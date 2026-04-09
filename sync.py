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

        # Erwartete Dateinamen aller aktiven Notices in WebDAV
        active_webdav_names: set[str] = set()
        for notice in notices:
            if notice.publish_start <= now and (notice.publish_end is None or now < notice.publish_end):
                base = Path(notice.stored_filename).stem
                for i in range(1, notice.page_count + 1):
                    active_webdav_names.add(f"{base}_p{i:03d}.jpg")

        # 1. Dateien in WebDAV, die keiner aktiven Notice angehören → löschen
        for name in list(webdav_files):
            if name not in active_webdav_names:
                delete_file(client, name)

        # 2. Abgelaufene Notices archivieren
        for notice in notices:
            if notice.publish_end is not None and notice.publish_end <= now:
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
