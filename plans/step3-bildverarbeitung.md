# Plan: Schritt 3 – Bildverarbeitung (Skalierung auf 4K)

## Ziel

Nach dem Upload wird jede Datei automatisch zu einem oder mehreren 4K-Bildern (3840×2160 px, JPEG) verarbeitet und im Verzeichnis `processed/` abgelegt. Bei PDFs wird jede Seite als eigene Datei gespeichert. Die Originaldatei in `uploads/` bleibt erhalten. Das Datenbankmodell bekommt ein `page_count`-Feld, damit der Sync-Job (Schritt 4) weiß, wie viele Dateien er pro Notice übertragen muss.

---

## Hintergrundwissen: Skalierungslogik

Das Bild wird **letterboxed** in einen schwarzen 3840×2160-Hintergrund eingepasst:
1. Erstelle eine schwarze 3840×2160-JPEG-Canvas
2. Skaliere das Quellbild mit `Image.LANCZOS` so, dass es **vollständig** in 3840×2160 passt (Seitenverhältnis erhalten, kein Zuschneiden)
3. Berechne die Position zum Zentrieren und paste das skalierte Bild auf die Canvas

---

## Änderungen am Datenbankmodell

### `app/models/notice.py` – Feld `page_count` ergänzen

```python
page_count: Mapped[int] = mapped_column(default=1)
```

Für JPEG/PNG ist `page_count` immer `1`. Für PDFs entspricht es der Seitenanzahl.

### Alembic-Migration

```bash
alembic revision --autogenerate -m "add page_count to notices"
alembic upgrade head
```

---

## Dateinamen-Konvention für verarbeitete Dateien

| Dateityp | Original in `uploads/` | Verarbeitet in `processed/` |
|---|---|---|
| JPEG/PNG | `{uuid}.jpg` | `{uuid}_p001.jpg` |
| PDF (3 Seiten) | `{uuid}.pdf` | `{uuid}_p001.jpg`, `{uuid}_p002.jpg`, `{uuid}_p003.jpg` |

Alle verarbeiteten Dateien sind immer JPEG, unabhängig vom Original.

---

## Implementierung `app/services/image.py`

```python
from pathlib import Path
from PIL import Image

TARGET_W, TARGET_H = 3840, 2160


def _letterbox(img: Image.Image) -> Image.Image:
    """Skaliert img auf 4K-Canvas mit schwarzem Hintergrund, kein Crop."""
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
    img = img.convert("RGB")
    img.thumbnail((TARGET_W, TARGET_H), Image.LANCZOS)
    x = (TARGET_W - img.width) // 2
    y = (TARGET_H - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def process_raster(src: Path, dest_dir: Path, base_name: str) -> int:
    """Verarbeitet eine JPEG/PNG-Datei → eine 4K-JPEG-Datei.
    Gibt die Seitenanzahl zurück (immer 1).
    """
    with Image.open(src) as img:
        result = _letterbox(img)
    out_path = dest_dir / f"{base_name}_p001.jpg"
    result.save(out_path, "JPEG", quality=92)
    return 1


def process_pdf(src: Path, dest_dir: Path, base_name: str) -> int:
    """Konvertiert jede PDF-Seite in eine 4K-JPEG-Datei.
    Gibt die Seitenanzahl zurück.
    """
    from pdf2image import convert_from_path

    pages = convert_from_path(str(src), dpi=150)
    for i, page in enumerate(pages, start=1):
        result = _letterbox(page)
        out_path = dest_dir / f"{base_name}_p{i:03d}.jpg"
        result.save(out_path, "JPEG", quality=92)
    return len(pages)


def process_upload(src: Path, dest_dir: Path, base_name: str, file_type: str) -> int:
    """Dispatcher: wählt die richtige Verarbeitungsfunktion anhand des Dateityps.
    Gibt die Seitenanzahl zurück.
    """
    if file_type == "pdf":
        return process_pdf(src, dest_dir, base_name)
    else:
        return process_raster(src, dest_dir, base_name)
```

**Hinweise:**
- `pdf2image` wird lazy importiert (nur bei PDFs), damit der Import-Fehler bei fehlendem `poppler-utils` erst beim Aufruf auftritt, nicht beim App-Start.
- `dpi=150` ergibt bei A4 ca. 1240×1754 px – ausreichend für den 4K-Letterbox.
- `quality=92` ist ein guter Kompromiss zwischen Qualität und Dateigröße.

---

## Integration in den Upload-Endpunkt

### `app/routers/upload.py` – nach dem Speichern der Originaldatei

Der Upload-Endpunkt wird um die Bildverarbeitung erweitert. Der `base_name` ist der UUID-Teil des `stored_filename` ohne Endung.

```python
from app.services.image import process_upload
from app.config import get_settings

settings = get_settings()

# … (nach dest.write_bytes(contents)):

base_name = Path(stored_name).stem          # UUID ohne Endung
page_count = process_upload(
    src=dest,
    dest_dir=Path(settings.processed_dir),
    base_name=base_name,
    file_type=db_notice.file_type,           # bereits normalisiert ("jpg"/"png"/"pdf")
)
db_notice.page_count = page_count
db.commit()
db.refresh(db_notice)
```

**Wichtig:** `process_upload` wird **nach** `db.commit()` des Notices aufgerufen, damit bei einem Fehler in der Bildverarbeitung der DB-Eintrag noch rollback-fähig ist. Die Reihenfolge im Endpunkt soll sein:

1. Datei auf Disk schreiben (`dest.write_bytes`)
2. DB-Eintrag anlegen und committen (ohne `page_count`, Default 1)
3. `process_upload` aufrufen
4. `db_notice.page_count = page_count` setzen und erneut committen

Bei einem Fehler in Schritt 3 wird eine `HTTPException` mit Status 500 geworfen. Der DB-Eintrag und die Originaldatei bleiben erhalten (für späteres Debugging oder Re-Processing).

---

## `NoticeResponse`-Schema anpassen

### `app/schemas/notice.py` – Feld `page_count` ergänzen

```python
class NoticeResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    file_type: str
    page_count: int          # neu
    publish_start: datetime
    publish_end: datetime
    archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `alembic upgrade head` fehlerfrei durchläuft und die Tabelle `notices` das Feld `page_count` enthält
2. Upload einer `.jpg`-Datei → `processed/{uuid}_p001.jpg` wird angelegt, `page_count=1` in der DB
3. Upload einer `.png`-Datei → analog zu JPEG
4. Upload einer mehrseitigen `.pdf`-Datei → `processed/{uuid}_p001.jpg`, `_p002.jpg` etc. werden angelegt, `page_count=n` in der DB
5. Alle erzeugten Dateien in `processed/` haben exakt die Abmessung 3840×2160 px (prüfbar z. B. mit `python3 -c "from PIL import Image; img=Image.open('processed/…_p001.jpg'); print(img.size)"`)
6. Der schwarze Balken (Letterbox) ist bei Bildern mit abweichendem Seitenverhältnis sichtbar
7. `GET /upload/` gibt `page_count` im Response zurück
