# Changelog

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
