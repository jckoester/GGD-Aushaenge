# Plan: Schritt 1 – Projektstruktur + FastAPI-Grundgerüst

## Ziel

Lauffähiges FastAPI-Projekt mit korrekter Verzeichnisstruktur, Konfigurationsverwaltung, Datenbankanbindung (SQLite via SQLAlchemy) und Alembic-Migrationsinfrastruktur. Noch keine Business-Logik – nur das Fundament für alle weiteren Schritte.

---

## Verzeichnisstruktur (Zielzustand)

```
ggd-aushaenge/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI-App, Lifespan-Handler
│   ├── config.py            # Einstellungen via pydantic-settings
│   ├── database.py          # SQLAlchemy Engine + Session
│   ├── models/
│   │   └── __init__.py      # Placeholder, Modelle kommen in Schritt 2
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── upload.py        # Placeholder
│   │   ├── archive.py       # Placeholder
│   │   └── sync.py          # Placeholder
│   └── services/
│       ├── __init__.py
│       ├── image.py         # Placeholder
│       └── webdav.py        # Placeholder
├── migrations/              # Alembic-Verzeichnis (via alembic init erzeugt)
├── uploads/                 # Hochgeladene Originaldateien (gitignored)
├── processed/               # 4K-verarbeitete Dateien (gitignored)
├── alembic.ini
├── requirements.txt
├── .env                     # Nicht einchecken
├── .env.example
└── .gitignore
```

---

## Aufgaben

### 1. `requirements.txt` erstellen

Folgende Pakete eintragen (ohne Versionspinning, außer bei bekannten Inkompatibilitäten):

```
fastapi
uvicorn[standard]
pydantic-settings
sqlalchemy
alembic
python-multipart
Pillow
pdf2image
webdavclient3
authlib
httpx
jinja2
python-dotenv
```

### 2. `.gitignore` erstellen

```
.env
uploads/
processed/
__pycache__/
*.pyc
*.db
.venv/
```

### 3. `.env.example` erstellen

Alle Konfigurationsvariablen mit Platzhalterwerten dokumentieren:

```
# Anwendung
SECRET_KEY=changeme

# Datenbankpfad (SQLite)
DATABASE_URL=sqlite:///./ggd_aushaenge.db

# Verzeichnisse
UPLOAD_DIR=uploads
PROCESSED_DIR=processed

# WebDAV
WEBDAV_URL=https://webdav.example.com/remote/path/
WEBDAV_USER=user
WEBDAV_PASSWORD=secret

# OIDC (wird in Schritt 6 befüllt)
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_SERVER_METADATA_URL=
OIDC_REQUIRED_GROUP=Infobildschirme
```

### 4. `app/config.py` erstellen

`pydantic-settings`-Klasse `Settings`, die alle Werte aus der `.env`-Datei lädt. Singleton-Pattern via `@lru_cache`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    secret_key: str
    database_url: str = "sqlite:///./ggd_aushaenge.db"
    upload_dir: str = "uploads"
    processed_dir: str = "processed"
    webdav_url: str
    webdav_user: str
    webdav_password: str
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_server_metadata_url: str = ""
    oidc_required_group: str = "Infobildschirme"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 5. `app/database.py` erstellen

SQLAlchemy-Engine und Session-Factory. `Base` für alle Modelle exportieren:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # nötig für SQLite
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 6. Placeholder-Router erstellen

Jede Datei unter `app/routers/` enthält einen leeren `APIRouter`, der später befüllt wird.

Beispiel `app/routers/upload.py`:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/upload", tags=["upload"])
```

Analog für `archive.py` (prefix `/archive`) und `sync.py` (prefix `/sync`).

### 7. `app/main.py` erstellen

- FastAPI-App mit Titel und Beschreibung
- Lifespan-Handler: beim Start `uploads/` und `processed/` anlegen falls nicht vorhanden
- Alle drei Router einbinden
- Health-Check-Endpunkt `GET /health` → `{"status": "ok"}`

```python
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from app.config import get_settings
from app.routers import upload, archive, sync

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.processed_dir).mkdir(exist_ok=True)
    yield

app = FastAPI(title="GGD Aushaenge", lifespan=lifespan)

app.include_router(upload.router)
app.include_router(archive.router)
app.include_router(sync.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

### 8. Alembic initialisieren

```bash
alembic init migrations
```

Danach `alembic.ini` und `migrations/env.py` anpassen:

- In `alembic.ini`: `sqlalchemy.url` entfernen (wird dynamisch gesetzt)
- In `migrations/env.py`:
  - `from app.database import Base, engine` importieren
  - `target_metadata = Base.metadata` setzen
  - `connectable = engine` in `run_migrations_online()` verwenden (statt aus config lesen)

### 9. Erste Alembic-Migration erstellen

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

Da noch keine Modelle existieren, erzeugt dies eine leere Migration – aber sie bestätigt, dass die Alembic-Infrastruktur funktioniert.

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `pip install -r requirements.txt` fehlerfrei durchläuft
2. Eine `.env`-Datei (nach `.env.example`) existiert mit gültigen Werten für `SECRET_KEY`, `WEBDAV_URL`, `WEBDAV_USER`, `WEBDAV_PASSWORD`
3. `alembic upgrade head` fehlerfrei durchläuft
4. `uvicorn app.main:app --reload` startet ohne Fehler
5. `GET /health` gibt `{"status": "ok"}` zurück
6. Die Verzeichnisse `uploads/` und `processed/` werden beim Start automatisch angelegt
