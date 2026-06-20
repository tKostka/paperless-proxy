# Paperless-NGX Proxy: Review, Schwachstellen und Architekturentscheidung

Datum: 2026-06-20
Repository: `tKostka/paperless-proxy`

## Ausgangslage

- Paperless-NGX läuft auf einem NAS und ist nur im lokalen Netzwerk erreichbar.
- Home Assistant läuft auf einem Raspberry Pi 5.
- Über das bestehende Nabu-Casa-Abo ist Home Assistant bereits sicher von außen erreichbar.
- Ziel ist gelegentlicher Zugriff auf Paperless von unterwegs, ohne zusätzlich VPN, Tailscale, Cloudflare Tunnel, Portfreigaben oder eine separate Public-Reverse-Proxy-Strecke einzurichten.
- Das Add-on stellt Paperless über Home-Assistant-Ingress bereit.

## Kurzfazit

Für gelegentliche Nutzung ist der Ansatz über Home Assistant und Nabu Casa grundsätzlich sinnvoll: kein zusätzlicher öffentlicher Dienst, keine Portfreigabe, keine zusätzliche Client-App, keine separate Authentifizierungsstrecke.

Die aktuelle Implementierung des Proxys ist aber HTTP-technisch zu fragil. Die Probleme beim Dokument-Viewer, insbesondere beim Eye-Icon / Preview / direktem Dokumentbetrachten, sind wahrscheinlich keine reinen CSS-Probleme. Kritischer sind HEAD-Requests, Content-Length, Range-/Partial-Content-Verhalten, vollständiges Puffern binärer Inhalte und zu breites Body-Rewriting.

Empfehlung: Den bestehenden Ansatz beibehalten, aber den Proxy stabilisieren. Erst wenn danach weiterhin regelmäßig Viewer-Probleme auftreten oder intensiver mobiler Zugriff gewünscht ist, sollte auf Tailscale oder eine direkte Reverse-Proxy-Lösung gewechselt werden.

## Relevante Code-Befunde

### 1. HEAD-Requests werden nicht sauber behandelt

`do_HEAD()` läuft durch denselben Pfad wie GET. `_send_response()` berechnet `Content-Length` anhand des gelesenen Bodys und schreibt anschließend immer den Body.

Problem:

- Bei HEAD darf kein Body gesendet werden.
- Wenn upstream bei HEAD keinen Body liefert, kann `Content-Length: 0` beim Client landen.
- PDF-/Dokumentviewer verwenden häufig HEAD oder Range-Requests zur Vorprüfung.
- Ein falscher Content-Length-Wert kann Inline-Viewer unzuverlässig machen.

Priorität: sehr hoch.

### 2. Binäre Antworten werden vollständig in RAM gelesen

Der Proxy macht aktuell `resp.read()` für alle Antworten, auch für PDFs, Bilder, Downloads und Preview-Dateien.

Problem:

- Große Dokumente werden komplett gepuffert.
- Mehrere parallele Viewer-Requests können RAM und Antwortzeit belasten.
- Range-/Partial-Content-Semantik wird unnötig riskant.

Priorität: sehr hoch.

### 3. JSON wird pauschal umgeschrieben

`rewrite_body()` verarbeitet neben HTML/CSS/JS auch `application/json`.

Problem:

- API-Antworten können Dokumentinhalte, Dateinamen, OCR-Text oder Metadaten enthalten.
- Strings wie `"/documents/"`, `"/api/"`, `"/media/"` können unbeabsichtigt verändert werden.
- Das ist keine Persistenz-Korruption, aber eine verfälschte Antwort an das Frontend.

Priorität: hoch.

### 4. URL-Rewriting ist heuristisch

Der Code ersetzt konkrete String-Muster wie `href="/`, `src="/`, `action="/` und einige JS-String-Pfade.

Nicht vollständig abgedeckt:

- `srcset`
- `poster`
- `formaction`
- CSS `url(/static/...)`
- escaped JSON
- absolute Paperless-URLs
- dynamisch gebaute URLs
- Web-Komponenten und künftige Paperless-Frontend-Änderungen

Priorität: mittel bis hoch.

### 5. Preview-Fix ist ein DOM-/CSS-Hack

Der Proxy injiziert CSS und JavaScript in HTML-Antworten, um Popover-Größe, `window.open()` und `target="_blank"` zu überschreiben.

Problem:

- Funktioniert nur solange Paperless dieselben Klassen und DOM-Strukturen verwendet.
- Mehrere Changelog-Einträge zeigen bereits iterative Reparaturen an Popover-Selektoren und Preview-Verhalten.
- CSS kann Viewer-Skalierung verbessern, aber auch neue Darstellungsfehler erzeugen.

Priorität: mittel.

### 6. Redirect-Rewriting ist zu aggressiv

Jede absolute `Location`-URL wird auf den Ingress-Pfad umgeschrieben.

Problem:

- Externe Redirects würden fälschlich lokalisiert.
- URL-Fragmente gehen verloren.
- Es wird nicht geprüft, ob die absolute URL tatsächlich zur Paperless-Origin gehört.

Priorität: mittel.

### 7. Fehlerantworten sind HTTP/1.1-unsauber

Im 502-Fall wird kein `Content-Length` gesetzt und die Verbindung nicht eindeutig geschlossen.

Problem:

- Browser oder WebViews können den Request als hängend interpretieren.
- Fehlersuche wird schwieriger.

Priorität: mittel.

### 8. Cookie-Rewriting ist naiv

`Set-Cookie` wird per einfachem String-Replacement geändert.

Problem:

- Case-Sensitivity.
- Varianten mit Leerzeichen oder abweichender Schreibweise werden nicht sicher erfasst.
- Komplexere Cookie-Attribute werden nicht strukturiert behandelt.

Priorität: niedrig bis mittel.

### 9. Base-Images verwenden `latest`

Die Add-on-Config verwendet Home-Assistant-Base-Images mit `latest`.

Problem:

- Builds sind nicht reproduzierbar.
- Upstream-Image-Änderungen können das Add-on ohne Codeänderung brechen.

Priorität: niedrig bis mittel.

## Empfohlene Umsetzung im bestehenden Proxy

### Phase 1: Viewer-Stabilität

1. HEAD korrekt implementieren:
   - Kein Body bei HEAD schreiben.
   - Upstream-Content-Length erhalten, wenn nicht rewritten wird.
   - `Content-Length` nur dann neu berechnen, wenn der Body tatsächlich verändert wurde.

2. Binary-Streaming einbauen:
   - PDFs, Bilder, Downloads, Thumbnails und Preview-Dateien nicht komplett puffern.
   - Header sauber weiterreichen.
   - `Range`, `Content-Range`, `Accept-Ranges`, `ETag`, `Last-Modified` erhalten.

3. Rewriting auf HTML/CSS/JS beschränken:
   - `application/json` aus `rewrite_body()` entfernen.
   - API-Antworten nicht blind verändern.

4. Range-/206-Verhalten testen:
   - `GET` ohne Range.
   - `HEAD`.
   - `GET` mit `Range: bytes=0-1023`.
   - Erwartung: korrekter Status, korrekter Content-Type, korrekter Content-Length bzw. Content-Range.

### Phase 2: Robustere URL- und Header-Behandlung

1. Redirect-Rewriting nur für Paperless-Origin und root-relative URLs.
2. URL-Fragmente erhalten.
3. `X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-For` bewusst setzen.
4. Cookie-Pfad case-insensitiv und kontrolliert umschreiben.
5. 502-Antworten mit `Content-Length` und optional `Connection: close` senden.

### Phase 3: Tests

Mindestens Unit-/Integrationstests für:

- `rewrite_location()` mit relativen, internen absoluten und externen URLs.
- `rewrite_body()` ohne JSON-Mutation.
- mehrere `Set-Cookie`-Header.
- HEAD auf PDF.
- GET PDF.
- GET PDF mit Range.
- 302 nach Login.
- Preview-/Download-/Thumbnail-Endpunkte.

## Architekturvarianten

### Variante A: Bestehender HA-Ingress-Proxy über Nabu Casa

Beschreibung:

- Paperless bleibt nur lokal erreichbar.
- HA ist über Nabu Casa erreichbar.
- Das Add-on proxyt Paperless über HA-Ingress.

Vorteile:

- Keine zusätzliche externe Angriffsfläche außer Home Assistant.
- Keine Portfreigabe.
- Kein VPN-Client notwendig.
- Kein zusätzlicher Dienst auf NAS oder Router.
- Nutzt bestehendes Nabu-Casa-Abo.
- Sehr passend für gelegentliche Nutzung.

Nachteile:

- Home Assistant wird zum Gateway für eine Nicht-HA-Anwendung.
- Ingress-Subpath ist für komplexe Web-Apps fragil.
- Viewer, PDFs, Range-Requests und Popups brauchen sauberes Proxy-Verhalten.
- Performance hängt zusätzlich vom Pi 5 und Nabu-Casa-Remote-Pfad ab.

Bewertung:

- Für gelegentliches Nachschauen von Dokumenten: sinnvoll.
- Für intensive Dokumentarbeit, große PDFs oder häufige Nutzung: nur bedingt optimal.

### Variante B: Tailscale

Beschreibung:

- NAS und Mobilgerät sind im privaten Tailnet.
- Paperless wird direkt über lokale NAS-Adresse oder MagicDNS erreicht.

Vorteile:

- Technisch sauberer als Subpath-/Ingress-Rewriting.
- Paperless läuft ohne Spezialproxy.
- Gute Sicherheit ohne öffentliche Portfreigabe.
- Kostenloser Personal-Plan ist für typische private Nutzung ausreichend.

Nachteile:

- Tailscale muss auf Mobilgerät und idealerweise NAS oder Router laufen.
- Extra Identitäts-/Netzwerkebene.
- Nicht so bequem wie einfach HA öffnen.
- Bei fremden Geräten nicht geeignet.

Bewertung:

- Beste technische Lösung, wenn App-Installation auf eigenen Geräten akzeptabel ist.
- Für gelegentliche Nutzung über bekannte eigene Geräte sehr stark.
- Kosten/Nutzen hoch, aber zusätzlicher Betriebsaufwand gegenüber Nabu-Casa-Weg.

### Variante C: Cloudflare Tunnel / Cloudflare Access

Beschreibung:

- Cloudflare Tunnel macht Paperless über eine öffentliche URL erreichbar.
- Cloudflare Access schützt davor mit Login/MFA/Policies.

Vorteile:

- Kein offener Port am Router.
- Gute Zugriffskontrolle möglich.
- Kein VPN-Client notwendig.
- Funktioniert auch von fremden Geräten im Browser.

Nachteile:

- Zusätzlicher externer Anbieter und Account.
- DNS/Domain/Access-Policy-Setup nötig.
- Paperless wird faktisch als eigene Web-App exponiert, auch wenn geschützt.
- Mehr Sicherheitsverantwortung als beim gelegentlichen HA-Ingress-Zugriff.

Bewertung:

- Sinnvoll, wenn Paperless regelmäßig von außen genutzt wird oder mehrere Nutzer Zugriff brauchen.
- Für gelegentliche Einzelnutzung wahrscheinlich unnötig komplex.

### Variante D: Direkter Reverse Proxy mit eigener Domain

Beschreibung:

- Nginx/Caddy/Traefik auf NAS, Router oder separatem Host.
- Eigene Domain, TLS, ggf. Authelia/Authentik/Basic Auth/MFA.

Vorteile:

- Web-technisch sauberste Lösung für Browserzugriff.
- Volle Kontrolle über Headers, TLS, Auth, Logging und Rate-Limits.
- Kein HA-Ingress-Subpath-Rewriting.

Nachteile:

- Öffentliche Angriffsfläche.
- Portfreigabe oder Tunnel nötig.
- Mehr Wartung.
- Authentifizierung muss sauber gelöst werden.
- Fehlerhafte Konfiguration kann Paperless direkt exponieren.

Bewertung:

- Für produktiven, häufigen Remote-Zugriff gut.
- Für gelegentliche private Nutzung meist Overkill.

### Variante E: Nur Paperless mobil per App / Sync

Beschreibung:

- Kein Webzugriff, sondern alternative Workflows: Dokumente lokal/Cloud, Export, Sync oder mobile App-Funktionalität je nach Bedarf.

Vorteile:

- Weniger Angriffsfläche.
- Geringer Betriebsaufwand.

Nachteile:

- Kein voller Paperless-Zugriff.
- Abhängig vom konkreten Nutzungsfall.

Bewertung:

- Nur sinnvoll, wenn unterwegs meist Dokumente gesucht/gelesen werden, aber keine Administration nötig ist.

## Entscheidungsempfehlung

### Empfehlung für den aktuellen Zweck

Den HA-Ingress/Nabu-Casa-Ansatz beibehalten, aber den Proxy gezielt härten.

Begründung:

- Das Ziel ist gelegentliche Nutzung von unterwegs.
- Nabu Casa ist bereits bezahlt und eingerichtet.
- Paperless bleibt lokal und wird nicht separat öffentlich gemacht.
- Der Zusatznutzen einer zweiten Remote-Zugriffslösung ist aktuell begrenzt.
- Die akuten Probleme sind wahrscheinlich im Proxy lösbar.

### Wann wechseln?

Auf Tailscale wechseln, wenn:

- Zugriff nur von eigenen Geräten erfolgen soll.
- Die Viewer-Probleme trotz Proxy-Fix weiter auftreten.
- größere PDFs regelmäßig geöffnet werden.
- auch andere lokale Dienste sauber erreichbar sein sollen.

Auf Cloudflare Tunnel oder direkten Reverse Proxy wechseln, wenn:

- Paperless häufig und komfortabel über normale Browser erreichbar sein soll.
- mehrere Nutzer Zugriff benötigen.
- fremde Geräte ohne VPN-Client unterstützt werden sollen.
- ein sauberer Public-Web-App-Betrieb gewünscht ist.

Nicht empfehlenswert:

- Paperless direkt per Portfreigabe ohne vorgeschaltete starke Authentifizierung und Härtung veröffentlichen.
- Paperless-Auto-Login bei direkter Internet-Exposition verwenden.

## Zielarchitektur für dieses Add-on

```text
Mobile Browser / HA App
        |
        | Nabu Casa Remote Access
        v
Home Assistant auf Raspberry Pi 5
        |
        | HA Ingress
        v
paperless-proxy Add-on
        |
        | lokales LAN
        v
Paperless-NGX auf NAS
```

Designprinzipien:

1. Paperless bleibt lokal.
2. Keine zusätzliche Portfreigabe.
3. Kein zusätzlicher VPN-Zwang.
4. Proxy verändert nur, was zwingend notwendig ist.
5. Binärdaten werden möglichst unverändert durchgereicht.
6. HTML-Rewriting ist Fallback, nicht Hauptmechanismus.
7. Viewer-/Preview-Endpunkte bekommen priorisierte Tests.

## Konkrete nächste Entwicklungsschritte

1. `proxy.py` refactoren:
   - Methode an `_send_response()` übergeben.
   - HEAD korrekt behandeln.
   - `should_rewrite()` einführen.
   - JSON-Rewriting entfernen.
   - Streaming-Pfad für nicht rewritebare Antworten einführen.

2. Test-Upstream hinzufügen:
   - kleiner lokaler HTTP-Server für HTML, JSON, PDF, Range, Redirects, Cookies.

3. Tests ergänzen:
   - Python `unittest` reicht aus, um keine zusätzlichen Dependencies einzuführen.

4. Dokumentation aktualisieren:
   - Klar sagen: gedacht für gelegentlichen Zugriff über HA/Nabu Casa.
   - Nicht als vollwertiger Public-Reverse-Proxy für Paperless positionieren.
   - Security-Hinweis zu `paperless_user` / Remote-User ergänzen.

5. Optional später:
   - Konfigurationsoption `rewrite_json: false` entfernen oder gar nicht einführen; JSON sollte standardmäßig nie rewrited werden.
   - Option `debug_headers: true` für Diagnose.
   - Healthcheck gegen `paperless_url`.

## Akzeptanzkriterien

- Dokumentliste lädt zuverlässig über Ingress.
- Eye-Icon / Preview öffnet Dokumente innerhalb HA, nicht extern ohne Session.
- PDF-Preview funktioniert bei kleinen und größeren PDFs.
- `HEAD` auf Dokumentendpunkte liefert plausible Header.
- `Range`-Requests liefern 206, wenn Paperless/upstream es unterstützt.
- JSON-Antworten werden nicht inhaltlich verändert.
- Keine unnötige Vollpufferung von PDFs/Bildern.
- Keine neuen Paperless-seitigen Pflichtkonfigurationsschritte für den Standardmodus.

## Schlussfolgerung

Die Idee ist für den beschriebenen Zweck richtig: bestehendes Nabu-Casa-Remote-Access als gelegentlichen sicheren Zugang nutzen und Paperless lokal halten.

Der Code muss aber weg vom HTML-/CSS-Hack als Problemlösung und hin zu korrektem Reverse-Proxy-Verhalten. Danach ist die Lösung pragmatisch, wartbar und für den privaten Use Case ausreichend. Tailscale bleibt die technisch sauberere Alternative, ist aber für den aktuellen Komfort- und Minimalaufwand-Ansatz nicht zwingend besser.
