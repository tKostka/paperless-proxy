# Paperless-NGX Proxy – Dokumentation

Dieses Addon fungiert als Reverse Proxy, der eine selbst gehostete **Paperless-NGX**-Instanz
über Home Assistants **Ingress**-System einbindet – inklusive Nabu Casa Remote-Zugriff.

---

## Voraussetzungen

- Paperless-NGX läuft im lokalen Netzwerk (z. B. per Docker/Portainer)
- Home Assistant kann die Paperless-Instanz per HTTP erreichen (gleicher Host oder LAN)

---

## 1. Paperless konfigurieren

Damit CSRF-Validierung und Redirects funktionieren, müssen folgende Umgebungsvariablen
in deinem Paperless `docker-compose.yml` gesetzt sein:

```yaml
environment:
  # Interne LAN-URL von Paperless
  - PAPERLESS_URL=http://192.168.7.221:8010

  # HA und dein Browser dürfen Anfragen senden
  - PAPERLESS_CSRF_TRUSTED_ORIGINS=http://192.168.7.221:8123,https://YOUR_NABU_CASA_ID.ui.nabu.casa

  # CORS für die HA-Integration (optional)
  - PAPERLESS_CORS_ALLOWED_HOSTS=http://192.168.7.221:8123
```

Danach Paperless neu starten:
```bash
docker compose down && docker compose up -d
```

---

## 2. Addon installieren

### Via GitHub-Repository (empfohlen)

1. HA → **Einstellungen → Add-ons → Add-on-Store**
2. Oben rechts: **⋮ → Repositories**
3. URL eintragen: `https://github.com/YOUR_USERNAME/hassio-paperless-proxy`
4. **Paperless-NGX Proxy** erscheint unter „YOUR_USERNAME"-Repository
5. Installieren

### Lokal (ohne GitHub)

Ordner `paperless-proxy/` nach `/addons/paperless_proxy/` auf dem HA-Host kopieren,
dann im Add-on-Store **Neu laden**.

---

## 3. Addon konfigurieren

Im Addon unter **Konfiguration**:

```yaml
paperless_url: "http://192.168.7.221:8010"
```

Dann **Starten**. In der HA-Seitenleiste erscheint der Eintrag **Paperless**.

---

## Nabu Casa / Remote-Zugriff

Sobald das Addon via Ingress läuft, ist Paperless automatisch über Nabu Casa erreichbar –
keine zusätzliche Portfreigabe oder VPN nötig.

---

## Bekannte Einschränkungen

| Problem | Ursache | Lösung |
|---|---|---|
| Login-Seite lädt, aber Redirect schlägt fehl | `PAPERLESS_CSRF_TRUSTED_ORIGINS` fehlt | Siehe Schritt 1 |
| Statische Assets (CSS/JS) laden nicht | Paperless gibt absolute URLs aus | `PAPERLESS_URL` korrekt setzen |
| Datei-Upload schlägt fehl | Body-Size-Limit | Bereits deaktiviert (`client_max_body_size 0`) |

---

## Troubleshooting

Logs des Addons anzeigen:

**HA → Einstellungen → Add-ons → Paperless-NGX Proxy → Protokoll**
