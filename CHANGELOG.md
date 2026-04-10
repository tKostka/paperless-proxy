# Changelog

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
