# Plan: Schritt 4 – WebDAV-Sync + Cron-Job

## Ziel

Ein Python-Skript `sync.py` (im Projektstamm, aufrufbar als `python sync.py`) führt den Abgleich zwischen der Datenbank und dem WebDAV-Ordner durch. Dieses Skript wird per Systemcron regelmäßig aufgerufen. Zusätzlich gibt es einen manuell auslösbaren HTTP-Endpunkt `POST /sync/run`, der dasselbe Skript per Subprocess startet (nützlich für Tests).

---

## Sync-Logik (aus den Anforderungen)

| Bedingung | Aktion |
|---|---|
| Datei in WebDAV, aber nicht in DB | Aus WebDAV löschen |
| Notice aktiv, noch nicht in WebDAV | Alle `processed/`-Dateien in WebDAV hochladen |
| Notice aktiv, bereits in WebDAV | Nichts tun |
| Notice abgelaufen | Aus WebDAV löschen, `archived = True` in DB setzen |
| Notice noch nicht gestartet | Nichts tun |

**„Aktiv"** bedeutet: `publish_start <= jetzt < publish_end` und `archived = False`.  
**„Abgelaufen"** bedeutet: `publish_end <= jetzt` und `archived = False`.

**Dateinamen in WebDAV:** Jede `processed/`-Datei (`{uuid}_p001.jpg` etc.) wird unter dem gleichen Dateinamen in WebDAV abgelegt. Die Zugehörigkeit einer WebDAV-Datei zu einer Notice ergibt sich aus dem UUID-Präfix.

---

## `app/services/webdav.py` implementieren

```python
from pathlib import Path
from webdav4.client import Client
from app.config import get_settings

def get_client() -> Client:
    settings = get_settings()
    return Client(
        base_url=settings.webdav_url,
        auth=(settings.webdav_user, settings.webdav_password),
    )

def list_files(client: Client) -> set[str]:
    """Gibt die Menge aller Dateinamen im WebDAV-Ordner zurück."""
    items = client.ls("", detail=False)
    return {Path(p).name for p in items if not p.endswith("/")}

def upload_file(client: Client, local_path: Path, remote_name: str) -> None:
    """Lädt eine lokale Datei in den WebDAV-Ordner hoch."""
    with open(local_path, "rb") as f:
        client.upload_fileobj(f, remote_name)

def delete_file(client: Client, remote_name: str) -> None:
    """Löscht eine Datei aus dem WebDAV-Ordner."""
    client.remove(remote_name)
```

**Hinweis:** `webdavclient3` aus `requirements.txt` stellt das Paket `webdav4` bereit. Der `Client` arbeitet relativ zu `base_url`, daher werden alle Pfade ohne führenden Slash übergeben.

---

## `sync.py` im Projektstamm erstellen

Das Skript wird direkt aufgerufen (`python sync.py`) und baut eine eigene DB-Session auf.

```python
#!/usr/bin/env python3
"""WebDAV-Sync: Abgleich zwischen Datenbank und WebDAV-Ordner."""

from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.models.notice import Notice
from app.services.webdav import delete_file, get_client, list_files, upload_file


def run_sync() -> None:
    settings = get_settings()
    processed_dir = Path(settings.processed_dir)
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # DB speichert naive UTC

    client = get_client()
    webdav_files = list_files(client)

    db = SessionLocal()
    try:
        notices = db.query(Notice).filter(Notice.archived == False).all()

        # UUID → Notice-Mapping für schnellen Lookup
        notice_by_uuid = {Path(n.stored_filename).stem: n for n in notices}

        # Erwartete Dateinamen aller aktiven Notices in WebDAV
        active_webdav_names: set[str] = set()
        for notice in notices:
            if notice.publish_start <= now < notice.publish_end:
                base = Path(notice.stored_filename).stem
                for i in range(1, notice.page_count + 1):
                    active_webdav_names.add(f"{base}_p{i:03d}.jpg")

        # 1. Dateien in WebDAV, die keiner aktiven Notice angehören → löschen
        for name in list(webdav_files):
            # UUID ist alles vor dem letzten "_p001"-Teil
            uuid_part = "_".join(name.removesuffix(".jpg").split("_")[:-1])
            if name not in active_webdav_names:
                delete_file(client, name)

        # 2. Abgelaufene Notices archivieren
        for notice in notices:
            if notice.publish_end <= now:
                notice.archived = True

        # 3. Aktive Notices hochladen, falls noch nicht in WebDAV
        for name in active_webdav_names:
            if name not in webdav_files:
                local_path = processed_dir / name
                if local_path.exists():
                    upload_file(client, local_path, name)

        db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    run_sync()
    print("Sync abgeschlossen.")
```

**Hinweise zur Implementierung:**
- Die DB speichert `datetime`-Werte ohne Timezone (naive UTC). `datetime.now(timezone.utc).replace(tzinfo=None)` erzeugt ebenfalls einen naiven UTC-Zeitstempel für den Vergleich.
- Schritt 1 löscht alle WebDAV-Dateien, die nicht zur aktiven Menge gehören – das deckt sowohl "nicht in DB" als auch "abgelaufen" ab, ohne die Fälle separat behandeln zu müssen.
- Schritt 2 setzt `archived = True` für alle abgelaufenen Notices (unabhängig davon, ob sie Dateien in WebDAV hatten).
- Schritt 3 lädt nur hoch, wenn die `processed/`-Datei lokal existiert (Schutz vor halbfertigen Uploads).

---

## `app/routers/sync.py` implementieren

Manuell auslösbarer Endpunkt für Tests:

```python
import subprocess
import sys
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/sync", tags=["sync"])

@router.post("/run", status_code=200)
def trigger_sync():
    """Löst den Sync-Job manuell aus (für Tests)."""
    result = subprocess.run(
        [sys.executable, "sync.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"status": "ok", "output": result.stdout}
```

---

## Cron-Job einrichten

Auf dem Produktionsserver via `crontab -e`:

```
*/5 * * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python sync.py >> /var/log/ggd-sync.log 2>&1
```

Das Intervall (hier 5 Minuten) ist anpassbar. Kein Eintrag in die App-Dateien nötig – das ist reine Server-Konfiguration.

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `python sync.py` läuft durch ohne Exception (auch wenn WebDAV leer ist)
2. Eine aktive Notice (Zeitraum aktiv) → ihre `processed/`-Dateien erscheinen nach dem Sync in WebDAV
3. Eine abgelaufene Notice → ihre Dateien werden aus WebDAV gelöscht, `archived = True` in DB
4. Eine Datei, die manuell in WebDAV liegt, aber keiner Notice gehört → wird gelöscht
5. Eine Notice, deren Startzeit noch nicht erreicht ist → keine Änderung in WebDAV
6. `POST /sync/run` liefert `{"status": "ok"}` und führt denselben Abgleich durch
