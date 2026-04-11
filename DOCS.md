# Paperless-NGX Proxy -- Documentation

This add-on acts as a reverse proxy that exposes a self-hosted **Paperless-NGX** instance
inside Home Assistant via **Ingress** -- including Nabu Casa remote access.

---

## Prerequisites

- Paperless-NGX is running on the local network (e.g. via Docker/Portainer)
- Home Assistant can reach the Paperless instance via HTTP (same host or LAN)

In the examples below, replace these placeholders with your own values:
- `192.168.1.100` -- IP address of the host running Paperless-NGX
- `8010` -- Port Paperless-NGX is listening on
- `your-id` -- Your Nabu Casa cloud ID (only relevant for remote access)

---

## 1. Paperless configuration (no changes required)

**Good news:** With v2.0+ of this add-on, **no Paperless-side configuration is required**.
The proxy spoofs the `Host`, `Origin` and `Referer` headers so Paperless sees the request
as coming from itself. CSRF and ALLOWED_HOSTS checks pass automatically.

If you previously had these set for an earlier version of this add-on, you can **remove them**:

```yaml
# These are NO LONGER needed with v2.0+:
# - PAPERLESS_URL=...
# - PAPERLESS_CSRF_TRUSTED_ORIGINS=...
```

### Optional: Auto-login via Remote-User

If you want to skip the Paperless login page entirely (HA's authentication is the access
control layer anyway), add this to your Paperless `docker-compose.yml`:

```yaml
environment:
  - PAPERLESS_ENABLE_HTTP_REMOTE_USER=true
```

Then restart Paperless:
```bash
docker compose down && docker compose up -d
```

You will configure the username on the add-on side (see step 3).

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
| `paperless_user` | No | Paperless username for auto-login (skips the login page) |

### Without auto-login

```yaml
paperless_url: "http://192.168.1.100:8010"
```

You will see the Paperless login page inside HA and log in manually.

### With auto-login (recommended for single-user setups)

```yaml
paperless_url: "http://192.168.1.100:8010"
paperless_user: "admin"
```

Requires `PAPERLESS_ENABLE_HTTP_REMOTE_USER=true` on Paperless (see step 1).

Then **Start**. A **Paperless** entry appears in the HA sidebar.

---

## Nabu Casa / Remote Access

Once the add-on runs via Ingress, Paperless is automatically reachable through Nabu Casa --
no additional port forwarding, VPN or firewall rules needed.

---

## Troubleshooting

View add-on logs:

**HA > Settings > Add-ons > Paperless-NGX Proxy > Log**

| Problem | Cause | Solution |
|---|---|---|
| 502 Proxy error | Paperless not reachable | Check `paperless_url` and that Paperless is running |
| Login succeeds but stays on login page | Browser cookie issue | Clear cookies for the HA domain and try again |
| CSRF errors on POST | Origin header issue | Open an issue — should not happen with v2.0+ |
| Auto-login does not work | `PAPERLESS_ENABLE_HTTP_REMOTE_USER` not set on Paperless | See step 1 |
