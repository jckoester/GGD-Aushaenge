# Plan: Schritt 2 – Datenbankmodell + Datei-Upload

## Ziel

SQLAlchemy-Modell für hochgeladene Dateien, Alembic-Migration, und einen funktionierenden Upload-Endpunkt, der Dateien entgegennimmt, auf dem Dateisystem speichert und einen Datenbankeintrag anlegt. Noch keine Bildverarbeitung (kommt in Schritt 3) – die Datei wird unverändert gespeichert.

---

## Datenbankmodell

### `app/models/notice.py` erstellen

```python
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_type: Mapped[str] = mapped_column(String(10))          # "jpg", "png", "pdf"
    publish_start: Mapped[datetime] = mapped_column(DateTime)
    publish_end: Mapped[datetime] = mapped_column(DateTime)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Felddefinitionen:**

- `original_filename` – Dateiname, wie vom Benutzer hochgeladen (nur zur Anzeige)
- `stored_filename` – eindeutiger Dateiname auf dem Dateisystem (z. B. UUID-basiert, mit Endung)
- `file_type` – Dateityp ohne Punkt (`jpg`, `png`, `pdf`)
- `publish_start` / `publish_end` – Veröffentlichungszeitraum, UTC
- `archived` – `True`, wenn die Datei ins Archiv verschoben wurde
- `created_at` – Zeitstempel des Uploads

### `app/models/__init__.py` aktualisieren

Das Modell dort importieren, damit Alembic es bei `autogenerate` erkennt:

```python
from app.models.notice import Notice
```

---

## Alembic-Migration

```bash
alembic revision --autogenerate -m "add notices table"
alembic upgrade head
```

Die generierte Migration muss die Tabelle `notices` mit allen Feldern enthalten.

---

## Pydantic-Schemas

### `app/schemas/notice.py` erstellen

Schemas für API-Requests und -Responses (getrennt von den ORM-Modellen):

```python
from datetime import datetime
from pydantic import BaseModel, model_validator

class NoticeCreate(BaseModel):
    publish_start: datetime
    publish_end: datetime

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeCreate":
        if self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self

class NoticeResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    file_type: str
    publish_start: datetime
    publish_end: datetime
    archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

### `app/schemas/__init__.py` erstellen

Leere Datei als Package-Marker.

---

## Upload-Endpunkt

### `app/routers/upload.py` implementieren

Endpunkt: `POST /upload/`

- Empfängt: `file` (UploadFile) + `publish_start` (Form-Feld) + `publish_end` (Form-Feld)
- Validiert: Dateityp muss `.jpg`, `.jpeg`, `.png` oder `.pdf` sein; sonst `400`
- Validiert: `publish_end` > `publish_start`; sonst `422`
- Speichert: Datei unter `{UPLOAD_DIR}/{uuid4()}.{ext}` (Originaldateiname wird nicht als Pfad verwendet)
- Legt DB-Eintrag an
- Gibt `NoticeResponse` zurück

```python
import uuid
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice
from app.schemas.notice import NoticeCreate, NoticeResponse

router = APIRouter(prefix="/upload", tags=["upload"])
settings = get_settings()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

@router.post("/", response_model=NoticeResponse, status_code=201)
async def upload_notice(
    file: UploadFile = File(...),
    publish_start: datetime = Form(...),
    publish_end: datetime = Form(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Dateityp '.{ext}' nicht erlaubt.")

    notice_data = NoticeCreate(publish_start=publish_start, publish_end=publish_end)

    stored_name = f"{uuid.uuid4()}.{ext}"
    dest = Path(settings.upload_dir) / stored_name

    contents = await file.read()
    dest.write_bytes(contents)

    db_notice = Notice(
        original_filename=file.filename,
        stored_filename=stored_name,
        file_type="jpg" if ext == "jpeg" else ext,
        publish_start=notice_data.publish_start,
        publish_end=notice_data.publish_end,
    )
    db.add(db_notice)
    db.commit()
    db.refresh(db_notice)
    return db_notice
```

**Hinweis zu `file_type`:** `.jpeg` wird auf `jpg` normalisiert, damit der Typ konsistent bleibt.

---

## Listen-Endpunkt

### `GET /upload/` – alle aktiven Einträge abrufen

Gibt alle nicht archivierten Notices zurück, sortiert nach `publish_start` absteigend:

```python
@router.get("/", response_model=list[NoticeResponse])
def list_notices(db: Session = Depends(get_db)):
    return (
        db.query(Notice)
        .filter(Notice.archived == False)
        .order_by(Notice.publish_start.desc())
        .all()
    )
```

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `alembic upgrade head` fehlerfrei durchläuft und die Tabelle `notices` in der SQLite-DB existiert
2. `uvicorn app.main:app --reload` startet ohne Fehler
3. `POST /upload/` mit einer gültigen `.jpg`-Datei und gültigen Datumsangaben:
   - gibt HTTP 201 zurück
   - legt die Datei unter `uploads/` ab
   - legt einen DB-Eintrag an (prüfbar über `GET /upload/`)
4. `POST /upload/` mit einer `.exe`-Datei gibt HTTP 400 zurück
5. `POST /upload/` mit `publish_end` < `publish_start` gibt HTTP 422 zurück
6. `GET /upload/` gibt die hochgeladenen Notices als JSON-Liste zurück
