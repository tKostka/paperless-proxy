"""Integration + unit tests for the Paperless-NGX Ingress proxy.

Spins up a fake Paperless upstream and the proxy in-process, then drives the
proxy with a raw HTTP client to assert correct reverse-proxy behaviour:

- HEAD on a PDF keeps the upstream Content-Length; HEAD on rewritten HTML omits it.
- GET PDF streams full bytes; GET PDF with Range yields 206 + Content-Range.
- application/json is passed through byte-for-byte (no OCR/content mutation).
- Redirects: root-relative and internal-absolute are prefixed (fragment kept),
  external redirects are left untouched.
- Multiple Set-Cookie headers survive; Path is rewritten case-insensitively.
- HTML gets <base href> prefixed and the preview CSS/JS injected; X-Frame-Options
  is replaced and CSP stripped.
- Upstream responses without Content-Length stream with Connection: close.
- Upstream failures produce a well-framed 502.

Run:  python3 -m unittest test_proxy -v   (no third-party deps)
"""
import http.client
import http.server
import os
import re
import threading
import unittest


INGRESS = '/api/hassio_ingress/TESTTOKEN'

# Binary payload with bytes that are NOT valid UTF-8 — exercises the
# pass-through (no-decode) path for PDFs/images.
PDF = b'%PDF-1.7\n' + bytes(range(256)) * 3 + b'\n%%EOF'

# JSON whose string values deliberately contain path-like substrings that the
# old blanket rewriter would have corrupted.
JSON_BODY = (
    b'{"id":1,"content":"OCR text mentions /api/ and href=\\"/x\\" and '
    b'/documents/3/ and src=\\"/y\\"","original_file_name":"/weird/name.pdf"}'
)

LOGIN_HTML = (
    b'<!DOCTYPE html><html><head><base href="/">'
    b'<link rel="stylesheet" href="/static/css/app.css">'
    b'<script src="/static/js/main.js"></script></head><body>'
    b'<form action="/accounts/login/" method="post"></form>'
    b'<a href="/api/documents/1/preview/" target="_blank">Eye</a>'
    b'<script>var u="/api/ui_settings/";fetch(u);</script>'
    b'</body></html>'
)

_UPSTREAM_NETLOC = None  # filled in once the upstream is bound


class _Upstream(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    # -- GET ---------------------------------------------------------------
    def do_GET(self):
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/accounts/login/?next=/')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Length', '0')
            self.end_headers()

        elif self.path == '/r-abs':
            self.send_response(302)
            self.send_header('Location',
                             f'http://{_UPSTREAM_NETLOC}/dashboard/#section')
            self.send_header('Content-Length', '0')
            self.end_headers()

        elif self.path == '/r-ext':
            self.send_response(302)
            self.send_header('Location',
                             'https://external.example.com/oauth?x=1#frag')
            self.send_header('Content-Length', '0')
            self.end_headers()

        elif self.path == '/r-scheme-rel':
            self.send_response(302)
            self.send_header('Location', f'//{_UPSTREAM_NETLOC}/dashboard/#srel')
            self.send_header('Content-Length', '0')
            self.end_headers()

        elif self.path == '/cached':
            # Conditional revalidation hit — 304 with no body, no Content-Length.
            self.send_response(304)
            self.send_header('ETag', '"pdf-etag"')
            self.end_headers()

        elif self.path == '/empty':
            self.send_response(204)
            self.end_headers()

        elif self.path.startswith('/accounts/login/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'")
            self.send_header('Set-Cookie', 'sessionid=abc123; Path=/; HttpOnly')
            self.send_header('Set-Cookie', 'csrftoken=xyz789; path=/; SameSite=Lax')
            self.send_header('Content-Length', str(len(LOGIN_HTML)))
            self.end_headers()
            self.wfile.write(LOGIN_HTML)

        elif self.path == '/api/documents/1/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(JSON_BODY)))
            self.end_headers()
            self.wfile.write(JSON_BODY)

        elif self.path.startswith('/api/documents/1/preview/'):
            rng = self.headers.get('Range')
            if rng:
                m = re.match(r'bytes=(\d+)-(\d*)', rng)
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else len(PDF) - 1
                chunk = PDF[start:end + 1]
                self.send_response(206)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Range',
                                 f'bytes {start}-{end}/{len(PDF)}')
                self.send_header('ETag', '"pdf-etag"')
                self.send_header('Content-Length', str(len(chunk)))
                self.end_headers()
                self.wfile.write(chunk)
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('ETag', '"pdf-etag"')
                # Some setups mark the preview as a download — proxy must force inline.
                self.send_header('Content-Disposition', 'attachment; filename="orig.pdf"')
                self.send_header('Content-Length', str(len(PDF)))
                self.end_headers()
                self.wfile.write(PDF)

        elif self.path == '/nolength':
            # HTTP/1.1 + Connection: close + no Content-Length → body framed by
            # connection close. urllib reads it to EOF with no Content-Length.
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Connection', 'close')
            self.close_connection = True
            self.end_headers()
            self.wfile.write(b'streamed-no-length-body')

        else:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()

    # -- HEAD --------------------------------------------------------------
    def do_HEAD(self):
        if self.path.startswith('/api/documents/1/preview/'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(len(PDF)))
            self.end_headers()
        elif self.path.startswith('/accounts/login/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(LOGIN_HTML)))
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()


# Module-level handles populated by setUpModule().
proxy = None
_upstream_server = None
_proxy_server = None
PROXY_HOST = '127.0.0.1'
PROXY_PORT = None


def setUpModule():
    global proxy, _upstream_server, _proxy_server, PROXY_PORT, _UPSTREAM_NETLOC

    _upstream_server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _Upstream)
    up_port = _upstream_server.server_address[1]
    _UPSTREAM_NETLOC = f'127.0.0.1:{up_port}'
    threading.Thread(target=_upstream_server.serve_forever, daemon=True).start()

    # proxy.py reads its config from the environment at import time.
    os.environ['PAPERLESS_URL'] = f'http://127.0.0.1:{up_port}'
    os.environ['INGRESS_ENTRY'] = INGRESS
    os.environ.pop('PAPERLESS_USER', None)

    import proxy as _proxy_mod
    proxy = _proxy_mod

    _proxy_server = proxy.ThreadingHTTPServer((PROXY_HOST, 0), proxy.ProxyHandler)
    PROXY_PORT = _proxy_server.server_address[1]
    threading.Thread(target=_proxy_server.serve_forever, daemon=True).start()


def tearDownModule():
    if _proxy_server:
        _proxy_server.shutdown()
    if _upstream_server:
        _upstream_server.shutdown()


def request(method, path, headers=None):
    """Issue one request to the proxy on a fresh connection."""
    conn = http.client.HTTPConnection(PROXY_HOST, PROXY_PORT, timeout=10)
    try:
        conn.request(method, path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, resp.getheaders(), body
    finally:
        conn.close()


def header(headers, name):
    """First header value matching name (case-insensitive), or None."""
    name = name.lower()
    for k, v in headers:
        if k.lower() == name:
            return v
    return None


def all_headers(headers, name):
    name = name.lower()
    return [v for k, v in headers if k.lower() == name]


class PureUnitTests(unittest.TestCase):
    """Direct function tests — no sockets."""

    def test_json_body_not_rewritten(self):
        self.assertEqual(proxy.rewrite_body(JSON_BODY, 'application/json'), JSON_BODY)

    def test_html_base_href_rewritten_and_injected(self):
        out = proxy.rewrite_body(LOGIN_HTML, 'text/html').decode()
        self.assertIn(f'<base href="{INGRESS}/">', out)
        self.assertIn(f'action="{INGRESS}/accounts/login/"', out)
        self.assertIn(f'href="{INGRESS}/api/documents/1/preview/"', out)
        self.assertIn('popover-preview', out)        # injected CSS
        self.assertIn('window.open', out)            # injected JS
        self.assertNotIn(f'{INGRESS}{INGRESS}', out)  # no double-prefix

    def test_location_root_relative(self):
        self.assertEqual(proxy.rewrite_location('/accounts/login/?next=/'),
                         INGRESS + '/accounts/login/?next=/')

    def test_location_internal_absolute_keeps_fragment(self):
        loc = f'http://{_UPSTREAM_NETLOC}/dashboard/#section'
        self.assertEqual(proxy.rewrite_location(loc), INGRESS + '/dashboard/#section')

    def test_location_external_untouched(self):
        loc = 'https://external.example.com/oauth?x=1#frag'
        self.assertEqual(proxy.rewrite_location(loc), loc)

    def test_location_scheme_relative_internal(self):
        loc = f'//{_UPSTREAM_NETLOC}/dashboard/#srel'
        self.assertEqual(proxy.rewrite_location(loc), INGRESS + '/dashboard/#srel')

    def test_location_scheme_relative_external(self):
        loc = '//external.example.com/x'
        self.assertEqual(proxy.rewrite_location(loc), loc)

    def test_cookie_path_case_insensitive(self):
        self.assertEqual(proxy.rewrite_cookie('a=b; Path=/; HttpOnly'),
                         f'a=b; Path={INGRESS}/; HttpOnly')
        self.assertEqual(proxy.rewrite_cookie('a=b; path=/'),
                         f'a=b; path={INGRESS}/')

    def test_is_rewritable_excludes_json(self):
        self.assertTrue(proxy.is_rewritable('text/html; charset=utf-8'))
        self.assertTrue(proxy.is_rewritable('application/javascript'))
        self.assertFalse(proxy.is_rewritable('application/json'))
        self.assertFalse(proxy.is_rewritable('application/pdf'))


class IntegrationTests(unittest.TestCase):

    def test_redirect_root_relative(self):
        status, headers, _ = request('GET', '/')
        self.assertEqual(status, 302)
        self.assertEqual(header(headers, 'Location'),
                         INGRESS + '/accounts/login/?next=/')

    def test_redirect_internal_absolute_fragment(self):
        status, headers, _ = request('GET', '/r-abs')
        self.assertEqual(status, 302)
        self.assertEqual(header(headers, 'Location'),
                         INGRESS + '/dashboard/#section')

    def test_redirect_external_untouched(self):
        status, headers, _ = request('GET', '/r-ext')
        self.assertEqual(status, 302)
        self.assertEqual(header(headers, 'Location'),
                         'https://external.example.com/oauth?x=1#frag')

    def test_redirect_scheme_relative_localised(self):
        status, headers, _ = request('GET', '/r-scheme-rel')
        self.assertEqual(status, 302)
        self.assertEqual(header(headers, 'Location'),
                         INGRESS + '/dashboard/#srel')

    def test_304_no_body_keeps_connection(self):
        status, headers, body = request('GET', '/cached')
        self.assertEqual(status, 304)
        self.assertEqual(body, b'')
        self.assertEqual(header(headers, 'ETag'), '"pdf-etag"')
        # 304 is self-framing → must NOT force a connection close.
        self.assertNotEqual((header(headers, 'Connection') or '').lower(), 'close')

    def test_204_no_body(self):
        status, headers, body = request('GET', '/empty')
        self.assertEqual(status, 204)
        self.assertEqual(body, b'')
        self.assertNotEqual((header(headers, 'Connection') or '').lower(), 'close')

    def test_login_html_rewrite_and_headers(self):
        status, headers, body = request('GET', '/accounts/login/')
        text = body.decode()
        self.assertEqual(status, 200)
        self.assertIn(f'<base href="{INGRESS}/">', text)
        self.assertIn('popover-preview', text)
        self.assertEqual(header(headers, 'X-Frame-Options'), 'SAMEORIGIN')
        self.assertIsNone(header(headers, 'Content-Security-Policy'))
        # Content-Length must match the rewritten (longer) body.
        self.assertEqual(int(header(headers, 'Content-Length')), len(body))

    def test_set_cookie_both_preserved_and_rewritten(self):
        _, headers, _ = request('GET', '/accounts/login/')
        cookies = all_headers(headers, 'Set-Cookie')
        self.assertEqual(len(cookies), 2)
        joined = ' '.join(cookies)
        self.assertIn(f'Path={INGRESS}/', joined)            # original case kept
        self.assertIn(f'path={INGRESS}/', joined)            # lowercase kept
        self.assertIn('sessionid=abc123', joined)
        self.assertIn('csrftoken=xyz789', joined)

    def test_json_passthrough_unchanged(self):
        status, headers, body = request('GET', '/api/documents/1/')
        self.assertEqual(status, 200)
        self.assertEqual(body, JSON_BODY)
        self.assertEqual(header(headers, 'Content-Type'), 'application/json')
        self.assertEqual(int(header(headers, 'Content-Length')), len(JSON_BODY))

    def test_pdf_get_full(self):
        status, headers, body = request('GET', '/api/documents/1/preview/')
        self.assertEqual(status, 200)
        self.assertEqual(body, PDF)
        self.assertEqual(int(header(headers, 'Content-Length')), len(PDF))
        self.assertEqual(header(headers, 'Accept-Ranges'), 'bytes')
        self.assertEqual(header(headers, 'X-Frame-Options'), 'SAMEORIGIN')

    def test_preview_forced_inline(self):
        # Upstream sends Content-Disposition: attachment; the proxy must replace
        # it with a single "inline" so the viewer renders it instead of downloading.
        status, headers, _ = request('GET', '/api/documents/1/preview/')
        self.assertEqual(status, 200)
        self.assertEqual(all_headers(headers, 'Content-Disposition'), ['inline'])

    def test_pdf_head_keeps_content_length_no_body(self):
        status, headers, body = request('HEAD', '/api/documents/1/preview/')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'')                                  # no body
        self.assertEqual(int(header(headers, 'Content-Length')), len(PDF))

    def test_html_head_omits_content_length(self):
        status, headers, body = request('HEAD', '/accounts/login/')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'')
        # Rewritable HTML → upstream length would be wrong, so it's omitted.
        self.assertIsNone(header(headers, 'Content-Length'))

    def test_pdf_range_206(self):
        status, headers, body = request(
            'GET', '/api/documents/1/preview/', headers={'Range': 'bytes=0-9'})
        self.assertEqual(status, 206)
        self.assertEqual(body, PDF[:10])
        self.assertEqual(int(header(headers, 'Content-Length')), 10)
        self.assertEqual(header(headers, 'Content-Range'),
                         f'bytes 0-9/{len(PDF)}')
        self.assertEqual(header(headers, 'Accept-Ranges'), 'bytes')

    def test_streaming_without_content_length(self):
        status, headers, body = request('GET', '/nolength')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'streamed-no-length-body')
        self.assertIsNone(header(headers, 'Content-Length'))
        self.assertEqual((header(headers, 'Connection') or '').lower(), 'close')

    def test_502_is_well_framed(self):
        orig = proxy._opener

        class _Boom:
            def open(self, *a, **k):
                raise ConnectionRefusedError('upstream down')

        proxy._opener = _Boom()
        try:
            status, headers, body = request('GET', '/')
        finally:
            proxy._opener = orig
        self.assertEqual(status, 502)
        self.assertIn(b'Proxy error', body)
        self.assertEqual(int(header(headers, 'Content-Length')), len(body))
        self.assertEqual((header(headers, 'Connection') or '').lower(), 'close')


if __name__ == '__main__':
    unittest.main(verbosity=2)
