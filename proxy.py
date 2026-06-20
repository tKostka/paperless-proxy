"""Paperless-NGX Ingress Proxy.

A lightweight reverse proxy that handles:
- Redirect rewriting (3xx Location headers → relative with Ingress prefix)
- HTML/JS/CSS URL rewriting (absolute paths → Ingress-prefixed paths)
- X-Frame-Options / CSP removal (allow iframe embedding in HA)
- Optional auto-authentication via Remote-User header

Design principles (see doc/remote-access-and-proxy-review.md):
- Binary/non-text responses (PDF, images, downloads, previews) are streamed
  through untouched — never fully buffered and never rewritten.
- Content-Length / Range / 206 semantics are preserved so inline document
  viewers work over Ingress.
- Only text/html, text/css and JavaScript are rewritten. JSON (API responses,
  OCR text, filenames) is passed through verbatim to avoid content corruption.
- HEAD requests carry no body and keep the upstream Content-Length.
"""
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse


PAPERLESS_URL = os.environ.get('PAPERLESS_URL', 'http://127.0.0.1:8010').rstrip('/')
INGRESS_ENTRY = os.environ.get('INGRESS_ENTRY', '').rstrip('/')
LISTEN_PORT = int(os.environ.get('INGRESS_PORT', '8099'))
PAPERLESS_USER = os.environ.get('PAPERLESS_USER', '')

_PAPERLESS = urlparse(PAPERLESS_URL)

# Stream upstream → client in chunks of this size for non-rewritable responses,
# so large PDFs/images are never fully buffered in RAM.
STREAM_CHUNK = 65536

# Content types whose body we rewrite (inject Ingress prefix + preview CSS/JS).
# NOTE: application/json is deliberately absent — API payloads (OCR text,
# filenames, document content) must never be mutated.
REWRITABLE_TYPES = (
    'text/html',
    'text/css',
    'application/javascript',
    'text/javascript',
)

# Headers to NOT forward from upstream to client.
STRIP_RESPONSE_HEADERS = {
    'x-frame-options',
    'content-security-policy',
    'content-length',       # set explicitly per response (rewritten vs passthrough)
    'transfer-encoding',     # hop-by-hop; we send Content-Length or close
    'connection',            # hop-by-hop; we manage keep-alive/close ourselves
    'server',                # Python adds its own
    'date',                  # Python adds its own
}

# Headers to NOT forward from client to upstream. Host is rewritten; the rest
# are hop-by-hop and must not be relayed (Content-Length is re-derived by urllib
# from the body we actually read).
STRIP_REQUEST_HEADERS = {
    'host',
    'connection', 'keep-alive', 'proxy-connection',
    'transfer-encoding', 'te', 'trailer', 'upgrade',
    'content-length',
}

# Case-insensitive "; Path=/" in a Set-Cookie value (group 1 keeps original case).
_COOKIE_PATH_RE = re.compile(r'(;\s*path=)/', re.IGNORECASE)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from following redirects — we handle them ourselves."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Global opener that does NOT follow redirects
_opener = urllib.request.build_opener(NoRedirectHandler)


def _effective_port(scheme: str, port) -> int:
    if port:
        return port
    return 443 if scheme == 'https' else 80


def _is_paperless_origin(parsed) -> bool:
    """True if an absolute/scheme-relative URL points at the Paperless origin.

    A scheme-relative URL (``//host/path``) inherits the upstream scheme so its
    default port resolves correctly (e.g. 443 for an https upstream).
    """
    scheme = parsed.scheme or _PAPERLESS.scheme
    return (parsed.hostname == _PAPERLESS.hostname
            and scheme == _PAPERLESS.scheme
            and (_effective_port(scheme, parsed.port)
                 == _effective_port(_PAPERLESS.scheme, _PAPERLESS.port)))


def rewrite_location(location: str) -> str:
    """Rewrite a Location header to a path with the Ingress prefix.

    - Root-relative (``/accounts/login/?next=/``) → prefix it.
    - Absolute URL on the Paperless origin → keep path+query+fragment, prefix it.
    - Absolute URL on any other origin (external redirect) → leave untouched.
    """
    if not INGRESS_ENTRY:
        return location

    parsed = urlparse(location)
    if parsed.scheme or parsed.netloc:
        if not _is_paperless_origin(parsed):
            return location  # external redirect — do not localise
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        if parsed.fragment:
            path += '#' + parsed.fragment
        return INGRESS_ENTRY + path

    if location.startswith('/'):
        # Raw string already contains any ?query/#fragment.
        return INGRESS_ENTRY + location
    return location


def rewrite_cookie(value: str) -> str:
    """Prefix the cookie Path with the Ingress entry (case-insensitive)."""
    if not INGRESS_ENTRY:
        return value
    value = _COOKIE_PATH_RE.sub(lambda m: m.group(1) + INGRESS_ENTRY + '/', value)
    # Guard against double-prefixing if upstream already used the Ingress path.
    value = value.replace(INGRESS_ENTRY + INGRESS_ENTRY, INGRESS_ENTRY)
    return value


def is_rewritable(content_type: str) -> bool:
    return any(t in content_type for t in REWRITABLE_TYPES)


# Injected into HTML <head> — keeps document preview/eye-icon inside the Ingress
# iframe (new windows lose the HA session) and makes the preview popover fit.
_INJECT_SCRIPT = '''<script>(function(){
var sameOrigin=function(u){try{return new URL(u,location.href).origin===location.origin;}catch(e){return false;}};
var o=window.open;
window.open=function(u,t,f){if(u&&sameOrigin(u)){location.href=new URL(u,location.href).href;return null;}return o.call(window,u,t,f);};
document.addEventListener('click',function(e){
var a=e.target.closest&&e.target.closest('a[target]');
if(!a)return;
var t=a.getAttribute('target');
if((t==='_blank'||t==='_new')&&a.href&&sameOrigin(a.href)){
e.preventDefault();e.stopPropagation();location.href=a.href;}
},true);
})();</script>'''

_INJECT_CSS = '''<style>
/* Paperless preview popover — base */
.popover.popover-preview{max-width:min(95vw,70rem)!important;}
.popover.popover-preview .popover-body{padding:0.25rem!important;overflow:hidden!important;height:auto!important;}
.preview-popup-container{max-width:100%!important;overflow:hidden!important;display:flex!important;align-items:center!important;justify-content:center!important;}
.preview-popup-container>*{width:min(90vw,65rem)!important;height:min(80vh,50rem)!important;max-width:100%!important;display:flex!important;align-items:center!important;justify-content:center!important;}
/* Inner viewers (PDF canvas, image, iframe) scale to fit container */
.preview-popup-container canvas,
.preview-popup-container img,
.preview-popup-container iframe{max-width:100%!important;max-height:100%!important;width:auto!important;height:auto!important;object-fit:contain!important;}
.preview-popup-container pngx-pdf-viewer,
.preview-popup-container pdf-viewer{display:flex!important;align-items:center!important;justify-content:center!important;width:100%!important;height:100%!important;}

/* Mobile: turn popover into a centered fixed overlay using full viewport */
@media(max-width:767.98px){
.popover.popover-preview{
position:fixed!important;
top:0.5rem!important;left:0.5rem!important;right:0.5rem!important;bottom:0.5rem!important;
max-width:none!important;width:auto!important;
transform:none!important;margin:0!important;
display:flex!important;flex-direction:column!important;
}
.popover.popover-preview>.popover-arrow{display:none!important;}
.popover.popover-preview .popover-body{flex:1 1 auto!important;min-height:0!important;}
.preview-popup-container{width:100%!important;height:100%!important;}
.preview-popup-container>*{width:100%!important;height:100%!important;}
}

/* Generic Bootstrap modals (document detail dialog, etc) */
.modal-title{word-wrap:break-word!important;overflow-wrap:anywhere!important;white-space:normal!important;}
.modal-dialog{max-width:min(98vw,1600px)!important;}
@media(max-width:767.98px){
.modal-dialog{max-width:100vw!important;margin:0.25rem!important;}
.modal-content{max-height:calc(100vh - 0.5rem)!important;}
}
@media(min-width:768px){
.modal-xl,.modal-lg{max-width:min(95vw,1600px)!important;}
}
</style>'''


def _rewrite_paths(text: str) -> str:
    """Prefix root-relative URLs in HTML/CSS/JS with the Ingress entry."""
    p = INGRESS_ENTRY

    # HTML attributes: href="/...", src="/...", action="/..."
    # (also rewrites <base href="/"> which the Angular frontend uses as its
    #  document.baseURI to build every API URL — the primary mechanism).
    text = text.replace('href="/', f'href="{p}/')
    text = text.replace("href='/", f"href='{p}/")
    text = text.replace('src="/', f'src="{p}/')
    text = text.replace("src='/", f"src='{p}/")
    text = text.replace('action="/', f'action="{p}/')
    text = text.replace("action='/", f"action='{p}/")

    # JS/CSS string paths: "/static/...", "/api/...", etc. Two-pass with a
    # sentinel so an already-prefixed path is not prefixed twice.
    known = ('static/', 'api/', 'accounts/', 'documents/',
             'dashboard/', 'media/', 'admin/')
    for path in known:
        text = text.replace(f'"{p}/{path}', f'"__INGRESS_DONE__/{path}')
        text = text.replace(f"'{p}/{path}", f"'__INGRESS_DONE__/{path}")
    for path in known:
        text = text.replace(f'"/{path}', f'"{p}/{path}')
        text = text.replace(f"'/{path}", f"'{p}/{path}")
    text = text.replace('__INGRESS_DONE__', p)

    # Clean up any remaining double-prefix.
    text = text.replace(p + p, p)
    return text


def rewrite_body(body: bytes, content_type: str) -> bytes:
    """Rewrite paths in HTML/CSS/JS and inject preview CSS/JS into HTML."""
    if not is_rewritable(content_type):
        return body
    try:
        text = body.decode('utf-8')
    except UnicodeDecodeError:
        return body  # not text we can safely touch — pass through unchanged

    if INGRESS_ENTRY:
        text = _rewrite_paths(text)

    if 'text/html' in content_type and '</head>' in text:
        text = text.replace('</head>', _INJECT_CSS + _INJECT_SCRIPT + '</head>', 1)

    return text.encode('utf-8')


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread."""
    daemon_threads = True


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that proxies requests to Paperless-NGX."""
    protocol_version = 'HTTP/1.1'

    def _proxy(self, method: str):
        target_url = PAPERLESS_URL + self.path

        # Read request body for POST/PUT/PATCH
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Build upstream request headers (preserve all values including duplicates)
        headers = {}
        for key, value in self.headers.items():
            if key.lower() not in STRIP_REQUEST_HEADERS:
                headers[key] = value

        # Set correct upstream Host and origin headers
        headers['Host'] = _PAPERLESS.netloc
        headers['Origin'] = PAPERLESS_URL
        headers['Referer'] = PAPERLESS_URL + '/'

        # Auto-authentication via Remote-User header
        if PAPERLESS_USER:
            headers['Remote-User'] = PAPERLESS_USER

        # Don't request compressed content (we may need to rewrite it)
        headers['Accept-Encoding'] = 'identity'

        req = urllib.request.Request(target_url, data=body, headers=headers, method=method)

        try:
            resp = _opener.open(req, timeout=300)
            self._relay(method, resp.status, resp)
        except urllib.error.HTTPError as e:
            # HTTPError is itself a readable response (headers + body).
            self._relay(method, e.code, e)
        except Exception as e:
            self._send_error(502, f'Proxy error: {e}')

    def _relay(self, method: str, status: int, resp):
        """Relay an upstream response to the client.

        Three paths:
        - Bodyless (HEAD, 1xx, 204, 304): headers only, no body, keep-alive safe.
        - Rewritable text (HTML/CSS/JS, non-redirect, non-206): buffer, rewrite,
          send with recomputed Content-Length.
        - Everything else (PDF, images, JSON, downloads, 206…): stream through.
        """
        headers = resp.headers
        content_type = headers.get('Content-Type', '')
        is_redirect = 300 <= status < 400
        rewritable = (not is_redirect and status != 206
                      and is_rewritable(content_type))

        # Responses that carry no body and are self-framing (RFC 7230 §3.3.3):
        # any HEAD, plus 1xx / 204 / 304. Keep-alive stays safe without a length,
        # so these never force a connection close (304s are frequent for cached
        # static assets — closing on each would churn the remote connection).
        if method == 'HEAD' or status in (204, 304) or 100 <= status < 200:
            cl = headers.get('Content-Length')
            # For a HEAD whose GET body we would rewrite, the upstream length no
            # longer matches — omit it rather than lie. Otherwise forward what
            # upstream advertised (informative; no body is sent either way).
            omit = cl is None or (method == 'HEAD' and rewritable)
            self._send_headers(status, headers,
                               content_length=None if omit else int(cl))
            return

        if rewritable:
            new_body = rewrite_body(resp.read(), content_type)
            self._send_headers(status, headers, content_length=len(new_body))
            self._write(new_body)
        else:
            cl = headers.get('Content-Length')
            if cl is not None:
                self._send_headers(status, headers, content_length=int(cl))
                self._stream(resp, expected=int(cl))
            else:
                # No length known → delimit the body by closing the connection.
                self._send_headers(status, headers, close=True)
                self._stream(resp)

    def _send_headers(self, status: int, headers, *,
                      content_length=None, close: bool = False):
        self.send_response(status)
        for key, value in headers.items():
            lk = key.lower()
            if lk in STRIP_RESPONSE_HEADERS:
                continue
            if lk == 'location':
                value = rewrite_location(value)
            elif lk == 'set-cookie':
                value = rewrite_cookie(value)
            self.send_header(key, value)

        # iframe-friendly (replaces upstream X-Frame-Options we stripped)
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        if content_length is not None:
            self.send_header('Content-Length', str(content_length))
        if close:
            self.send_header('Connection', 'close')
            self.close_connection = True
        self.end_headers()

    def _stream(self, resp, expected=None):
        """Copy the upstream body to the client in chunks.

        If ``expected`` (the forwarded Content-Length) is given and upstream
        ends short — or a read fails mid-body — close the connection so a
        keep-alive client doesn't hang waiting for or desync on missing bytes.
        """
        sent = 0
        while True:
            try:
                chunk = resp.read(STREAM_CHUNK)
            except Exception:
                self.close_connection = True
                break
            if not chunk:
                break
            if not self._write(chunk):
                break
            sent += len(chunk)
        if expected is not None and sent < expected:
            self.close_connection = True
        return sent

    def _write(self, data: bytes) -> bool:
        try:
            self.wfile.write(data)
            return True
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
            return False

    def _send_error(self, status: int, message: str):
        body = message.encode('utf-8', 'replace')
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.close_connection = True
        self.end_headers()
        self._write(body)
        sys.stdout.write(f'[proxy] ERROR: {message}\n')
        sys.stdout.flush()

    def do_GET(self): self._proxy('GET')
    def do_POST(self): self._proxy('POST')
    def do_PUT(self): self._proxy('PUT')
    def do_DELETE(self): self._proxy('DELETE')
    def do_PATCH(self): self._proxy('PATCH')
    def do_HEAD(self): self._proxy('HEAD')
    def do_OPTIONS(self): self._proxy('OPTIONS')

    def log_message(self, fmt, *args):
        msg = fmt % args
        sys.stdout.write(f'[proxy] {msg}\n')
        sys.stdout.flush()


def main():
    print(f'[proxy] Paperless-NGX Ingress Proxy')
    print(f'[proxy] Target:       {PAPERLESS_URL}')
    print(f'[proxy] Ingress path: {INGRESS_ENTRY}')
    print(f'[proxy] Listen port:  {LISTEN_PORT}')
    if PAPERLESS_USER:
        print(f'[proxy] Auto-login:   {PAPERLESS_USER} (Remote-User)')
    else:
        print(f'[proxy] Auto-login:   disabled')
    print(f'[proxy] Starting...')

    server = ThreadingHTTPServer(('0.0.0.0', LISTEN_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('[proxy] Shutting down')
        server.server_close()


if __name__ == '__main__':
    main()
