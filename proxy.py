"""Paperless-NGX Ingress Proxy.

A lightweight reverse proxy that handles:
- Redirect rewriting (302 Location headers → relative with Ingress prefix)
- HTML/JS/CSS URL rewriting (absolute paths → Ingress-prefixed paths)
- X-Frame-Options removal (allow iframe embedding in HA)
- Optional auto-authentication via Remote-User header
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

# Headers to NOT forward from upstream to client
STRIP_RESPONSE_HEADERS = {
    'x-frame-options',
    'content-security-policy',
    'content-length',       # recalculated after rewriting
    'transfer-encoding',    # we send full body, not chunked
    'connection',
    'server',               # Python adds its own
    'date',                 # Python adds its own
}

# Headers to NOT forward from client to upstream
STRIP_REQUEST_HEADERS = {'host'}


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from following redirects — we handle them ourselves."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Global opener that does NOT follow redirects
_opener = urllib.request.build_opener(NoRedirectHandler)


def rewrite_location(location: str) -> str:
    """Rewrite a Location header to be a relative path with Ingress prefix."""
    parsed = urlparse(location)
    if parsed.scheme:
        # Absolute URL: http://192.168.1.100:8010/accounts/login/?next=/
        path = parsed.path
        if parsed.query:
            path += '?' + parsed.query
        return INGRESS_ENTRY + path
    # Relative URL: /accounts/login/?next=/
    if location.startswith('/'):
        return INGRESS_ENTRY + location
    return location


def rewrite_body(body: bytes, content_type: str) -> bytes:
    """Rewrite absolute paths in response body to include Ingress prefix."""
    if not INGRESS_ENTRY:
        return body
    if not any(ct in content_type for ct in
               ('text/html', 'text/css', 'application/javascript', 'application/json')):
        return body
    try:
        text = body.decode('utf-8')
    except UnicodeDecodeError:
        return body

    p = INGRESS_ENTRY

    # HTML attributes: href="/...", src="/...", action="/..."
    text = text.replace('href="/', f'href="{p}/')
    text = text.replace("href='/", f"href='{p}/")
    text = text.replace('src="/', f'src="{p}/')
    text = text.replace("src='/", f"src='{p}/")
    text = text.replace('action="/', f'action="{p}/')
    text = text.replace("action='/", f"action='{p}/")

    # JS/CSS string paths: "/static/...", "/api/...", etc.
    for path in ('static/', 'api/', 'accounts/', 'documents/',
                 'dashboard/', 'media/', 'admin/'):
        text = text.replace(f'"{p}/{path}', f'"__INGRESS_DONE__/{path}')
        text = text.replace(f"'{p}/{path}", f"'__INGRESS_DONE__/{path}")

    for path in ('static/', 'api/', 'accounts/', 'documents/',
                 'dashboard/', 'media/', 'admin/'):
        text = text.replace(f'"/{path}', f'"{p}/{path}')
        text = text.replace(f"'/{path}", f"'{p}/{path}")

    text = text.replace('__INGRESS_DONE__', p)

    # Clean up any remaining double-prefix
    text = text.replace(p + p, p)

    # Inject script + CSS into HTML responses
    if 'text/html' in content_type and '</head>' in text:
        # Script: keep navigation inside the Ingress iframe so document
        # preview doesn't open in an external browser (which has no HA session)
        script = '''<script>(function(){
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

        # CSS: make Paperless preview popover responsive inside Ingress iframe.
        css = '''<style>
/* Paperless preview popover — base */
.popover.popover-preview{max-width:min(95vw,70rem)!important;}
.popover.popover-preview .popover-body{padding:0.25rem!important;overflow:hidden!important;}
.preview-popup-container{max-width:100%!important;overflow:hidden!important;}
.preview-popup-container>*{width:min(90vw,65rem)!important;height:min(75vh,45rem)!important;max-width:100%!important;}
/* Inner viewers (PDF canvas, image, iframe) must scale to container */
.preview-popup-container canvas,
.preview-popup-container img,
.preview-popup-container iframe,
.preview-popup-container pngx-pdf-viewer,
.preview-popup-container pdf-viewer{max-width:100%!important;}
.preview-popup-container pngx-pdf-viewer,
.preview-popup-container pdf-viewer{display:block;width:100%!important;height:100%!important;}

/* Mobile: turn popover into a centered fixed overlay */
@media(max-width:767.98px){
.popover.popover-preview{
position:fixed!important;
top:0.5rem!important;left:0.5rem!important;right:0.5rem!important;bottom:0.5rem!important;
max-width:none!important;width:auto!important;
transform:none!important;margin:0!important;
}
.popover.popover-preview>.popover-arrow{display:none!important;}
.preview-popup-container{width:100%!important;height:100%!important;}
.preview-popup-container>*{width:100%!important;height:calc(100vh - 4rem)!important;}
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

        text = text.replace('</head>', css + script + '</head>', 1)

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
        parsed = urlparse(PAPERLESS_URL)
        headers['Host'] = parsed.netloc
        headers['Origin'] = PAPERLESS_URL
        headers['Referer'] = PAPERLESS_URL + '/'

        # Auto-authentication via Remote-User header
        if PAPERLESS_USER:
            headers['Remote-User'] = PAPERLESS_USER

        # Don't request compressed content (we need to rewrite it)
        headers['Accept-Encoding'] = 'identity'

        req = urllib.request.Request(target_url, data=body, headers=headers, method=method)

        try:
            resp = _opener.open(req, timeout=300)
            self._send_response(resp.status, resp.headers, resp.read())
        except urllib.error.HTTPError as e:
            self._send_response(e.code, e.headers, e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            msg = f'Proxy error: {e}'
            self.wfile.write(msg.encode())
            sys.stdout.write(f'[proxy] ERROR: {msg}\n')
            sys.stdout.flush()

    def _send_response(self, status: int, headers, body: bytes):
        content_type = ''
        for key, value in headers.items():
            if key.lower() == 'content-type':
                content_type = value
                break

        # Rewrite body if applicable (only for non-redirect responses)
        if status < 300 or status >= 400:
            body = rewrite_body(body, content_type)

        self.send_response(status)

        # Forward headers with modifications
        # Use items() to get ALL header values including duplicate Set-Cookie
        for key, value in headers.items():
            lk = key.lower()
            if lk in STRIP_RESPONSE_HEADERS:
                continue

            # Rewrite Location header for redirects
            if lk == 'location':
                value = rewrite_location(value)

            # Rewrite Set-Cookie paths
            if lk == 'set-cookie' and INGRESS_ENTRY:
                value = value.replace('Path=/', f'Path={INGRESS_ENTRY}/')
                # Fix double-prefix in cookie path
                value = value.replace(
                    f'Path={INGRESS_ENTRY}{INGRESS_ENTRY}',
                    f'Path={INGRESS_ENTRY}')

            self.send_header(key, value)

        # Add iframe-friendly header
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
