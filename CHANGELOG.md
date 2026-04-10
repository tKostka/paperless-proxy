# Changelog

## 2.0.0

- **Breaking**: Replaced nginx with Python reverse proxy for reliable Ingress support
- Fixed: Redirect rewriting now uses relative paths (no more port 8099 in URLs)
- Fixed: HTML/JS/CSS URL rewriting without double-prefixing
- Fixed: Set-Cookie path rewriting for Ingress
- Added: `paperless_user` option for auto-login via Remote-User header
- Added: X-Frame-Options and CSP header stripping for iframe embedding
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
