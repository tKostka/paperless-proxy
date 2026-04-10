# Paperless-NGX Proxy

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FtKostka%2Fpaperless-proxy)

Home Assistant Add-on: Reverse Proxy for [Paperless-NGX](https://docs.paperless-ngx.com/) via Ingress.

## What it does

This add-on runs a reverse proxy that exposes a self-hosted Paperless-NGX instance inside the Home Assistant sidebar through Ingress. No additional port forwarding or VPN required -- works with Nabu Casa remote access out of the box.

## Installation

1. Click the button above, or manually add this repository URL in **Settings > Add-ons > Add-on Store > Repositories**:
   ```
   https://github.com/tKostka/paperless-proxy
   ```
2. Install **Paperless-NGX Proxy** from the store
3. Configure (see below)
4. Start the add-on

## Configuration

| Option | Required | Description |
|---|---|---|
| `paperless_url` | Yes | Full URL of your Paperless-NGX instance (e.g. `http://192.168.1.100:8010`) |
| `paperless_user` | No | Paperless username for auto-login (skips login page) |

For auto-login, also set `PAPERLESS_ENABLE_HTTP_REMOTE_USER=true` in your Paperless config.
See [DOCS.md](DOCS.md) for full setup instructions.

## Supported Architectures

- aarch64
- amd64
- armv7

## License

[MIT](LICENSE)
