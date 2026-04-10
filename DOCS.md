# Paperless-NGX Proxy -- Documentation

This add-on acts as a reverse proxy that exposes a self-hosted **Paperless-NGX** instance
inside Home Assistant via **Ingress** -- including Nabu Casa remote access.

---

## Prerequisites

- Paperless-NGX is running on the local network (e.g. via Docker/Portainer)
- Home Assistant can reach the Paperless instance via HTTP (same host or LAN)

---

## 1. Configure Paperless

Add the following environment variables to your Paperless `docker-compose.yml`:

```yaml
environment:
  # Internal LAN URL of Paperless
  - PAPERLESS_URL=http://YOUR_PAPERLESS_IP:YOUR_PAPERLESS_PORT

  # Allow requests from HA and Nabu Casa
  - PAPERLESS_CSRF_TRUSTED_ORIGINS=http://YOUR_HA_IP:8123,https://YOUR_NABU_CASA_ID.ui.nabu.casa

  # (Optional) Enable auto-login through the proxy — no login page needed
  - PAPERLESS_ENABLE_HTTP_REMOTE_USER=true
```

Replace the placeholders:
- `YOUR_PAPERLESS_IP` -- IP address of your Paperless host (e.g. `192.168.1.100`)
- `YOUR_PAPERLESS_PORT` -- Port Paperless is running on (e.g. `8010`)
- `YOUR_HA_IP` -- IP address of your Home Assistant instance
- `YOUR_NABU_CASA_ID` -- Your Nabu Casa cloud ID (only needed for remote access)

Then restart Paperless:
```bash
docker compose down && docker compose up -d
```

---

## 2. Install the Add-on

### Via GitHub Repository (recommended)

1. In HA go to **Settings > Add-ons > Add-on Store**
2. Top right menu: **Repositories**
3. Add URL: `https://github.com/tKostka/paperless-proxy`
4. **Paperless-NGX Proxy** appears in the store
5. Install

### Local (without GitHub)

Copy the `paperless-proxy/` folder to `/addons/paperless_proxy/` on the HA host,
then reload the Add-on Store.

---

## 3. Configure the Add-on

In the add-on under **Configuration**:

| Option | Required | Description |
|---|---|---|
| `paperless_url` | Yes | Full URL of your Paperless instance (e.g. `http://192.168.1.100:8010`) |
| `paperless_user` | No | Paperless username for auto-login (requires `PAPERLESS_ENABLE_HTTP_REMOTE_USER=true` on Paperless side) |

### Without auto-login

```yaml
paperless_url: "http://YOUR_PAPERLESS_IP:YOUR_PAPERLESS_PORT"
```

You will see the Paperless login page inside HA and log in manually.

### With auto-login (recommended)

```yaml
paperless_url: "http://YOUR_PAPERLESS_IP:YOUR_PAPERLESS_PORT"
paperless_user: "your_paperless_username"
```

Requires `PAPERLESS_ENABLE_HTTP_REMOTE_USER=true` in your Paperless config (see step 1).
This skips the login page entirely -- HA's own authentication is the access control layer.

Then **Start**. A **Paperless** entry appears in the HA sidebar.

---

## Nabu Casa / Remote Access

Once the add-on runs via Ingress, Paperless is automatically reachable through Nabu Casa --
no additional port forwarding or VPN needed.

---

## Troubleshooting

View add-on logs:

**HA > Settings > Add-ons > Paperless-NGX Proxy > Log**

| Problem | Cause | Solution |
|---|---|---|
| Login page shows but redirect fails | Redirect URL rewriting issue | Set `paperless_user` + enable `PAPERLESS_ENABLE_HTTP_REMOTE_USER` to skip login |
| Static assets (CSS/JS) not loading | Paperless returns absolute URLs | Set `PAPERLESS_URL` correctly in Paperless config |
| 502 Proxy error | Paperless not reachable | Check `paperless_url` and that Paperless is running |
