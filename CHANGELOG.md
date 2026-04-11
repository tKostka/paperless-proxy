# Changelog

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
