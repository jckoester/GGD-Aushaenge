# GGD Aushaenge

Webanwendung zur Verwaltung von digitalen Aushängen (Infoscreens).

---

## Voraussetzungen

- Python 3.11+
- `poppler-utils` und `fonts-dejavu-core` (für PDF-Verarbeitung und RSS-Rendering): `apt install poppler-utils fonts-dejavu-core`
- Zugang zu einem WebDAV-Server
- IServ-Installation mit OAuth2/OIDC-Unterstützung

---

## Installation

```bash
git clone <repo-url>
cd GGD-Aushaenge

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Konfiguration

`.env`-Datei im Projektverzeichnis anlegen:

```env
# Pflichtfelder
SECRET_KEY=<langer zufälliger String, z.B. openssl rand -hex 32>
WEBDAV_URL=https://<server>/webdav/<ordner>
WEBDAV_USER=<benutzer>
WEBDAV_PASSWORD=<passwort>

# OIDC (IServ)
OIDC_CLIENT_ID=<client-id>
OIDC_CLIENT_SECRET=<client-secret>
OIDC_SERVER_METADATA_URL=https://<iserv-domain>/.well-known/openid-configuration

# Optional (Standardwerte)
DATABASE_URL=sqlite:///./ggd_aushaenge.db
UPLOAD_DIR=uploads
PROCESSED_DIR=processed
OIDC_REQUIRED_GROUP=infobildschirm

# RSS-Feed (optional)
RSS_FEED_URL=https://gymnasium-ditzingen.de/iserv/public/news/rss/1
RSS_ENABLED=true

# Lokaler Entwicklungsmodus – Login-Zwang deaktivieren (niemals auf dem Produktionsserver setzen!)
# DEV_MODE=true
```

#### Entwicklungsmodus (`DEV_MODE`)

Mit `DEV_MODE=true` wird der OIDC-Login vollständig überbrückt: Die App läuft
ohne erreichbaren IServ-Provider und meldet automatisch einen synthetischen
Testnutzer an. `GET /login` schreibt diesen direkt in die Session und leitet
auf `/` weiter.

Im Entwicklungsmodus können die OIDC-Variablen leer bleiben. Für WebDAV
genügen Dummy-Werte, falls kein lokaler Server vorhanden ist:

```env
DEV_MODE=true
SECRET_KEY=dev-secret
WEBDAV_URL=http://localhost:5005/
WEBDAV_USER=dev
WEBDAV_PASSWORD=dev
```

### IServ OAuth2-Anwendung einrichten

In IServ unter **Verwaltung → OAuth2-Anwendungen** eine neue Anwendung anlegen:

- Redirect-URI: `https://<domain>/auth/callback`
- Scopes: `openid`, `profile`, `email`, `groups`
- Den generierten `client_id` und `client_secret` in die `.env` eintragen

---

## Datenbank initialisieren

```bash
source venv/bin/activate
alembic upgrade head
```

---

## Starten

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=<PROXY_IP>
```

Für den Produktionsbetrieb empfiehlt sich ein systemd-Service hinter nginx als Reverse Proxy.

---

## systemd-Service einrichten

Service-Datei anlegen (Pfade ggf. anpassen):

```bash
sudo nano /etc/systemd/system/ggd-aushaenge.service
```

```ini
[Unit]
Description=GGD Aushaenge – Digitale Aushänge Verwaltung
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/pfad/zum/projekt
EnvironmentFile=/pfad/zum/projekt/.env
ExecStart=/pfad/zum/projekt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=<PROXY_IP>
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Service aktivieren und starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ggd-aushaenge
sudo systemctl start ggd-aushaenge
```

Status prüfen:

```bash
sudo systemctl status ggd-aushaenge
```

---

## Cron-Job einrichten

Der Sync-Job gleicht die Datenbank mit dem WebDAV-Ordner ab. Er muss auf dem Server als Systemcron eingerichtet werden.

```bash
crontab -e
```

Folgenden Eintrag hinzufügen (Pfade anpassen):

```cron
*/5 * * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python sync.py >> /var/log/ggd-sync.log 2>&1
```

Das Intervall (hier 5 Minuten) ist nach Bedarf anpassbar.

### Was der Sync-Job tut

- Dateien im WebDAV-Ordner ohne zugehörige aktive Notice → werden gelöscht
- Notices, deren Veröffentlichungszeitraum abgelaufen ist → werden archiviert
- Aktive Notices, deren Dateien noch nicht im WebDAV-Ordner liegen → werden hochgeladen

### Manuell ausführen

```bash
python sync.py
```

Oder über die Web-Oberfläche mit dem **Sync**-Button in der Navigation.

---

## RSS-Feed-Sync einrichten

Der RSS-Sync liest den konfigurierten Feed und legt neue Nachrichten automatisch
als Aushänge an. Er läuft als eigenständiges Script mit eigenem Cron-Eintrag:

```bash
crontab -e
```

Folgenden Eintrag hinzufügen (Pfade anpassen):

```cron
*/15 * * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python rss_sync.py >> /var/log/ggd-rss.log 2>&1
```

Das Intervall (hier 15 Minuten) ist unabhängig vom WebDAV-Sync (5 Minuten).

Mit `RSS_ENABLED=false` in `.env` lässt sich der RSS-Sync deaktivieren, ohne
den Cron-Eintrag entfernen zu müssen.

### Was der RSS-Sync tut

- Einträge im Feed, die noch nicht in der DB sind → werden als Aushang angelegt
  und als 4K-Bild gerendert
- Einträge, die aus dem Feed verschwunden sind → bekommen `publish_end = jetzt`;
  der WebDAV-Sync archiviert sie beim nächsten Lauf
- Bereits bekannte Einträge → werden ignoriert (Duplikaterkennung via `guid`)

### Manuell ausführen

```bash
python rss_sync.py
```
