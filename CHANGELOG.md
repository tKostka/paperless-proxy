# Changelog

## 2.3.0

Document preview: readable + zoomable on mobile (Pixel Fold etc.). The eye-icon
popover rendered the PDF page **fit-to-fit** (`object-fit: contain`), so a
portrait page in a landscape window shrank to the window height — tiny text and
big empty side margins — with no way to zoom.

- Changed: the preview popover now **fits the width and scrolls vertically**
  instead of fitting the whole page. Text renders much larger and the wasted
  side/top margins are gone. pdf.js renders the canvas at the (now wide)
  container size, so it stays sharp.
- Added: **zoom** in the preview — `+` / `-` buttons (top-right of the popover)
  and double-tap toggle. Scaling is by width so the scroll container pans, and
  it stays crisp up to the device pixel ratio (~3x on a modern phone) because
  pdf.js renders the canvas backing store at `devicePixelRatio`.
- Added: the document preview endpoint (`/api/documents/<id>/preview/`) is now
  served with `Content-Disposition: inline`, so a setup that marks it as an
  attachment shows it in the viewer instead of triggering a download.
- Note: zoom is done on the existing canvas (no native-PDF/iframe routing),
  which keeps it reliable inside the Home Assistant Ingress iframe and the
  Companion-app WebView on Android, where embedded native PDF rendering is
  unreliable.

## 2.2.0

Reverse-proxy hardening — fixes recurring document-viewer/preview problems at the
HTTP layer instead of papering over them with CSS. See
`doc/remote-access-and-proxy-review.md` for the analysis.

- Fixed: `HEAD` requests no longer write a body and no longer report
  `Content-Length: 0`. Binary endpoints (PDF / preview / thumbnail / download)
  now keep the upstream `Content-Length`, which inline PDF viewers probe before
  loading — a likely root cause of the flaky document preview.
- Fixed: PDFs, images and downloads are now **streamed** instead of being fully
  buffered in RAM, and `Range` requests work — `206 Partial Content` with
  `Content-Range` / `Accept-Ranges` / `ETag` / `Last-Modified` is passed through
  untouched. Large PDFs and seek-in-viewer now load reliably.
- Fixed: `application/json` (API responses) is no longer rewritten. OCR text,
  filenames and document content that happened to contain path-like strings
  (`/api/`, `/documents/`, `href="/…"`) could be silently corrupted. Navigation
  still works because the Angular frontend builds every API URL from the
  (rewritten) `<base href>`, not from JSON fields.
- Fixed: `206 Partial Content` bodies are never rewritten.
- Fixed: redirect (`Location`) rewriting only touches the Paperless origin —
  external redirects are left intact — and now preserves URL fragments (`#…`).
- Fixed: `502` errors are correctly framed (`Content-Length` + `Connection: close`)
  so browsers / WebViews don't hang on a failed upstream.
- Fixed: `Set-Cookie` `Path` rewriting is now case-insensitive.
- Changed: hop-by-hop request headers (`Connection`, `Transfer-Encoding`, `TE`,
  `Upgrade`, …) are no longer forwarded upstream.
- Added: `test_proxy.py` — a dependency-free `unittest` suite (fake upstream +
  in-process proxy) covering HEAD/GET/Range on PDF, JSON passthrough, redirect
  rewriting, multiple `Set-Cookie`, no-length streaming and 502 framing.
- Kept: the preview-popover CSS and the `window.open` / `target="_blank"` capture
  as a secondary cosmetic layer.

## 2.1.5

- Fixed: Empty space below the PDF in the preview popover. The canvas
  rendered at its natural pixel size and didn't fill the available
  height. Now uses object-fit: contain so the PDF scales to fit the
  whole popover area while preserving aspect ratio.
- Use flex centering throughout the popover hierarchy.

## 2.1.4

- Fixed: Preview popover overflow on smartphone — PDF/canvas inside the
  popover was rendered at fixed width and overflowed. Now scales canvas/img/
  iframe/pdf-viewer to 100% of container.
- Fixed: On mobile (<768px), preview popover is now a centered fixed overlay
  (no longer anchored to the eye button) so it can use the full screen.
- Tablet: bumped popover max width from 60rem to 70rem.

## 2.1.3

- Fixed: Document preview was a Paperless popover (`.popover-preview`),
  not a modal — previous CSS targeted the wrong selectors. Now overrides
  Paperless's hardcoded `.preview-popup-container > *` (30rem×22rem) and
  `.popover.popover-preview` (32rem) with viewport-based sizes.

## 2.1.2

- Fixed: Document preview modal sizing inside Ingress iframe
  - Smartphone: long titles forced modal wider than viewport, cutting off the right side. Now wraps title and caps modal at 100vw.
  - Tablet/desktop: modal-xl was capped at Bootstrap's 1140px while the iframe was wider. Now uses up to 95vw.

## 2.1.1

- Fixed: Document preview eye icon — Paperless uses `<a target="_blank">`
  not `window.open()`, so the previous fix didn't help. Now also intercepts
  clicks on same-origin links with `target="_blank"` and navigates within
  the current frame instead.

## 2.1.0

- Fixed: Document preview (eye icon) opening external browser → 401
  Inject `window.open()` override that redirects same-origin URLs into
  the current iframe instead of opening a new tab/external browser.
  This was breaking document viewing in the HA Companion App where
  new windows lose the HA session.

## 2.0.2

- **No more Paperless-side config**: `PAPERLESS_CSRF_TRUSTED_ORIGINS` and `PAPERLESS_URL` are no longer required because the proxy spoofs Host/Origin/Referer headers
- **Breaking**: Replaced nginx with Python reverse proxy for reliable Ingress support
- Fixed: Redirect rewriting now uses relative paths (no more port 8099 in URLs)
- Fixed: HTML/JS/CSS URL rewriting without double-prefixing
- Fixed: Set-Cookie path rewriting for Ingress
- Fixed: Preserve all Set-Cookie headers (sessionid was lost with duplicate keys)
- Fixed: HTTP/1.1 protocol for HA Supervisor compatibility
- Added: `paperless_user` option for auto-login via Remote-User header
- Added: X-Frame-Options and CSP header stripping for iframe embedding
- Added: ThreadingHTTPServer for concurrent request handling
- Removed: nginx and all nginx modules (no longer needed)

## 1.2.0

- Fixed: Use HA base image with S6-Overlay (fixes "can only run as pid 1" error)
- Fixed: Proper S6 service registration (run.sh as /etc/services.d/ service)
- Fixed: bashio shebang (`#!/usr/bin/with-contenv bashio`)
- Added: `build_from` for all architectures
- Added: `repository.yaml` for HA add-on store
- Added: Input validation for `paperless_url`
- Added: Icons (icon.png, logo.png)
- Added: One-click install badge in README
- Removed: Hardcoded IP addresses from documentation

## 1.0.0

- Initial release
