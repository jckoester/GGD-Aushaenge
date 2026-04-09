# Plan: Schritt 7 – Dauerhafte Aushänge ohne Ablaufdatum

## Ziel

`publish_end` wird optional (nullable). `NULL` bedeutet „kein Ablaufdatum – Aushang bleibt dauerhaft aktiv". Betroffen sind: Datenbankmodell, Alembic-Migration, Pydantic-Schemas, Sync-Job.

---

## 1. Datenbankmodell: `app/models/notice.py`

`publish_end` auf nullable setzen:

```python
publish_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

---

## 2. Alembic-Migration

```bash
alembic revision --autogenerate -m "make publish_end nullable"
alembic upgrade head
```

**Achtung:** SQLite unterstützt kein `ALTER COLUMN`. Alembic erzeugt für SQLite eine „batch migration" (Tabelle neu erstellen). Das funktioniert automatisch, wenn in `migrations/env.py` `render_as_batch=True` gesetzt ist.

`migrations/env.py` – `context.configure()`-Aufruf in `run_migrations_online()` anpassen:

```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,
)
```

---

## 3. Pydantic-Schemas: `app/schemas/notice.py`

`publish_end` in allen drei Schemas auf `datetime | None` ändern. Der Validator prüft `end > start` nur wenn `publish_end` gesetzt ist:

```python
class NoticeCreate(BaseModel):
    publish_start: datetime
    publish_end: datetime | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeCreate":
        if self.publish_end is not None and self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self


class NoticeUpdate(BaseModel):
    publish_start: datetime
    publish_end: datetime | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeUpdate":
        if self.publish_end is not None and self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self


class NoticeResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    file_type: str
    page_count: int
    publish_start: datetime
    publish_end: datetime | None
    archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## 4. Sync-Job: `sync.py`

Zwei Stellen müssen angepasst werden:

**„Aktiv"-Bedingung** (Zeile 28): `publish_end` kann `None` sein → `None` bedeutet kein Ablaufdatum, also immer aktiv solange `publish_start` erreicht:

```python
# vorher:
if notice.publish_start <= now < notice.publish_end:

# nachher:
if notice.publish_start <= now and (notice.publish_end is None or now < notice.publish_end):
```

**„Abgelaufen"-Bedingung** (Zeile 40): nur archivieren wenn `publish_end` gesetzt und überschritten:

```python
# vorher:
if notice.publish_end <= now:

# nachher:
if notice.publish_end is not None and notice.publish_end <= now:
```

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `alembic upgrade head` fehlerfrei durchläuft
2. `POST /upload/` ohne `publish_end` (oder `publish_end: null`) legt einen Eintrag mit `publish_end = null` an
3. `POST /upload/` mit `publish_end` funktioniert weiterhin wie bisher
4. `POST /upload/` mit `publish_end <= publish_start` gibt weiterhin HTTP 422 zurück
5. Eine Notice mit `publish_end = null` wird vom Sync-Job nicht archiviert
6. Eine Notice mit `publish_end = null` wird vom Sync-Job hochgeladen, sobald `publish_start` erreicht ist
7. `GET /upload/` gibt `publish_end: null` für dauerhafte Aushänge zurück
