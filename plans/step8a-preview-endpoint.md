# Plan: Schritt 8a – Vorschau-Endpunkt

## Ziel

Neuer Endpunkt `GET /files/{notice_id}/preview` liefert die erste verarbeitete Seite einer Notice als JPEG. Wird später für Thumbnails in der UI verwendet.

---

## Neuer Router `app/routers/files.py`

```python
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{notice_id}/preview", response_class=FileResponse)
def preview(notice_id: int, db: Session = Depends(get_db)):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    settings = get_settings()
    base = Path(notice.stored_filename).stem
    path = Path(settings.processed_dir) / f"{base}_p001.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Vorschaubild nicht gefunden.")
    return FileResponse(path, media_type="image/jpeg")
```

## `app/main.py` – Router einbinden

```python
from app.routers import upload, archive, sync, files

app.include_router(files.router)
```

---

## Verifikation

1. `GET /files/{id}/preview` einer vorhandenen Notice liefert HTTP 200 mit `Content-Type: image/jpeg`
2. `GET /files/{id}/preview` mit unbekannter ID liefert HTTP 404
