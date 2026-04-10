# Paperless-NGX Proxy -- Documentation

This add-on acts as a reverse proxy that exposes a self-hosted **Paperless-NGX** instance
inside Home Assistant via **Ingress** -- including Nabu Casa remote access.

---

## Prerequisites

- Paperless-NGX is running on the local network (e.g. via Docker/Portainer)
- Home Assistant can reach the Paperless instance via HTTP (same host or LAN)

---

## 1. Configure Paperless

For CSRF validation and redirects to work, the following environment variables must be set
in your Paperless `docker-compose.yml`:

```yaml
environment:
  # Internal LAN URL of Paperless
  - PAPERLESS_URL=http://YOUR_PAPERLESS_IP:YOUR_PAPERLESS_PORT

  # HA and your browser may send requests
  - PAPERLESS_CSRF_TRUSTED_ORIGINS=http://YOUR_HA_IP:8123,https://YOUR_NABU_CASA_ID.ui.nabu.casa

  # CORS for the HA integration (optional)
  - PAPERLESS_CORS_ALLOWED_HOSTS=http://YOUR_HA_IP:8123
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

```yaml
paperless_url: "http://YOUR_PAPERLESS_IP:YOUR_PAPERLESS_PORT"
```

Then **Start**. A **Paperless** entry appears in the HA sidebar.

---

## Nabu Casa / Remote Access

Once the add-on runs via Ingress, Paperless is automatically reachable through Nabu Casa --
no additional port forwarding or VPN needed.

---

## Known Limitations

| Problem | Cause | Solution |
|---|---|---|
| Login page loads but redirect fails | `PAPERLESS_CSRF_TRUSTED_ORIGINS` missing | See step 1 |
| Static assets (CSS/JS) not loading | Paperless returns absolute URLs | Set `PAPERLESS_URL` correctly |
| File upload fails | Body size limit | Already disabled (`client_max_body_size 0`) |

---

## Troubleshooting

View add-on logs:

**HA > Settings > Add-ons > Paperless-NGX Proxy > Log**
