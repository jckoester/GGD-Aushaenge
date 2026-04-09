# Plan: Schritt 5 – Archiv-Funktionen

## Ziel

Die drei Archiv-API-Endpunkte implementieren: archivierte Notices auflisten, eine archivierte Notice erneut veröffentlichen, eine archivierte Notice dauerhaft löschen (inkl. Dateien). Das Frontend kommt in Schritt 7.

---

## `app/routers/archive.py` implementieren

**Import-Block:**

```python
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice
from app.schemas.notice import NoticeCreate, NoticeResponse

router = APIRouter(prefix="/archive", tags=["archive"])
```

### `GET /archive/` – alle archivierten Notices

```python
@router.get("/", response_model=list[NoticeResponse])
def list_archive(db: Session = Depends(get_db)):
    return (
        db.query(Notice)
        .filter(Notice.archived == True)
        .order_by(Notice.publish_end.desc())
        .all()
    )
```

### `POST /archive/{notice_id}/republish` – Notice erneut veröffentlichen

Setzt `archived = False` und überschreibt `publish_start` / `publish_end` mit neuen Werten. Verwendet `NoticeCreate` für die Validierung (inkl. `end > start`).

```python
@router.post("/{notice_id}/republish", response_model=NoticeResponse)
def republish(
    notice_id: int,
    data: NoticeCreate,
    db: Session = Depends(get_db),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    if not notice.archived:
        raise HTTPException(status_code=400, detail="Notice ist nicht archiviert.")
    notice.archived = False
    notice.publish_start = data.publish_start
    notice.publish_end = data.publish_end
    db.commit()
    db.refresh(notice)
    return notice
```

### `DELETE /archive/{notice_id}` – Notice dauerhaft löschen

Löscht DB-Eintrag, Originaldatei aus `uploads/` und alle verarbeiteten Dateien aus `processed/`. Nur für archivierte Notices erlaubt.

```python
@router.delete("/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db)):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    if not notice.archived:
        raise HTTPException(status_code=400, detail="Nur archivierte Notices können gelöscht werden.")

    settings = get_settings()
    base = Path(notice.stored_filename).stem

    Path(settings.upload_dir, notice.stored_filename).unlink(missing_ok=True)
    for i in range(1, notice.page_count + 1):
        Path(settings.processed_dir, f"{base}_p{i:03d}.jpg").unlink(missing_ok=True)

    db.delete(notice)
    db.commit()
```

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `GET /archive/` gibt eine Liste archivierter Notices zurück (kann leer sein)
2. Eine abgelaufene Notice (nach Sync) taucht in `GET /archive/` auf und nicht mehr in `GET /upload/`
3. `POST /archive/{id}/republish` mit gültigem Zeitraum setzt `archived = False` und gibt die Notice zurück
4. `POST /archive/{id}/republish` mit `publish_end <= publish_start` gibt HTTP 422 zurück
5. `POST /archive/{id}/republish` auf eine nicht-archivierte Notice gibt HTTP 400 zurück
6. `DELETE /archive/{id}` entfernt den DB-Eintrag sowie die Dateien aus `uploads/` und `processed/`
7. `DELETE /archive/{id}` auf eine nicht-archivierte Notice gibt HTTP 400 zurück
