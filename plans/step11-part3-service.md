# Step 11 / Teil 3: Service und Script – `rss.py` und `rss_sync.py`

Voraussetzung: Teil 1 (Modell, Migration, Config) und Teil 2 (render_news) sind abgeschlossen.

---

## 1. `app/services/rss.py` (neue Datei)

```python
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import mktime
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from lxml import html as lhtml
from PIL import Image
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.notice import Notice
from app.services.image import render_news


def _extract_images(description_html: str, base_url: str) -> list:
    """Lädt alle <img>-Bilder aus der HTML-Description als PIL-Images."""
    if not description_html:
        return []
    doc = lhtml.fromstring(description_html)
    result = []
    for src in doc.xpath("//img/@src"):
        url = urljoin(base_url, src)
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            img.load()
            result.append(img.convert("RGB"))
        except Exception as e:
            print(f"  Bild nicht ladbar ({url}): {e}")
    return result


def _extract_text(description_html: str) -> str:
    """Gibt den Klartext der HTML-Description zurück (HTML-Tags entfernt)."""
    if not description_html:
        return ""
    doc = lhtml.fromstring(description_html)
    return doc.text_content().strip()


def sync_feed(db: Session) -> tuple[int, int]:
    """
    Liest den RSS-Feed und gleicht ihn mit der DB ab:
    - Neue Einträge → Notice anlegen + rendern
    - Verschwundene Einträge → publish_end auf jetzt setzen

    Gibt (added, removed) zurück.
    """
    settings = get_settings()
    if not settings.rss_enabled:
        return 0, 0

    feed = feedparser.parse(settings.rss_feed_url)

    parsed_url = urlparse(settings.rss_feed_url)
    feed_base = f"{parsed_url.scheme}://{parsed_url.netloc}/"

    # Bestehende aktive RSS-Notices aus DB
    existing: dict[str, Notice] = {
        n.external_id: n
        for n in db.query(Notice).filter(
            Notice.source == "rss", Notice.archived == False
        ).all()
    }

    feed_ids: set[str] = set()
    added = 0

    for entry in feed.entries:
        external_id: str = entry.get("id") or entry.get("link", "")
        if not external_id:
            continue
        feed_ids.add(external_id)

        if external_id in existing:
            continue  # bereits bekannt

        title: str = entry.get("title", "Ohne Titel")
        desc_html: str = entry.get("description", "") or entry.get("summary", "")
        body_text = _extract_text(desc_html)
        images = _extract_images(desc_html, feed_base)

        # Veröffentlichungsdatum aus pubDate, Fallback auf jetzt
        published = entry.get("published_parsed")
        if published:
            pub_dt = datetime.fromtimestamp(
                mktime(published), tz=timezone.utc
            ).replace(tzinfo=None)
        else:
            pub_dt = datetime.utcnow()

        stored_name = f"{uuid.uuid4()}.rss"
        base_name = Path(stored_name).stem
        processed_dir = Path(settings.processed_dir)

        try:
            page_count = render_news(
                title=title,
                body_text=body_text,
                images=images,
                dest_dir=processed_dir,
                base_name=base_name,
            )
        except Exception as e:
            print(f"  Rendering fehlgeschlagen für '{title}': {e}")
            continue

        notice = Notice(
            original_filename=title,
            stored_filename=stored_name,
            file_type="rss",
            publish_start=pub_dt,
            publish_end=None,
            page_count=page_count,
            source="rss",
            external_id=external_id,
        )
        db.add(notice)
        added += 1

    # Verschwundene Einträge beenden (WebDAV-Sync archiviert sie dann automatisch)
    removed = 0
    now = datetime.utcnow()
    for ext_id, notice in existing.items():
        if ext_id not in feed_ids:
            notice.publish_end = now
            removed += 1

    db.commit()
    return added, removed
```

### Hinweise zur Implementierung

- `feedparser.parse()` blockiert (synchron) — das ist hier gewollt, da
  `rss_sync.py` als eigenständiges Script läuft, nicht innerhalb von FastAPI.
- `lhtml.fromstring()` erfordert einen nicht-leeren String; die Leerstring-Prüfung
  am Anfang von `_extract_text` und `_extract_images` deckt das ab.
- Bilder werden mit `img.load()` vor dem Schließen des `BytesIO`-Puffers vollständig
  geladen — ohne `load()` wäre das Bild beim späteren Zugriff ungültig.
- RSS-Notices haben `file_type="rss"` und keine echte Datei in `upload_dir`.
  `archive.py`'s `DELETE`-Route ruft `unlink(missing_ok=True)` auf — das ist
  korrekt und benötigt keinen Fix.

---

## 2. `rss_sync.py` (neue Datei im Projektroot)

Analog zu `sync.py` im Projektroot:

```python
#!/usr/bin/env python3
"""RSS-Feed-Sync: Neue News-Einträge als Aushänge anlegen, verschwundene beenden."""

from app.database import SessionLocal
from app.services.rss import sync_feed


def run() -> None:
    db = SessionLocal()
    try:
        added, removed = sync_feed(db)
        print(f"RSS-Sync abgeschlossen: {added} neu, {removed} beendet.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
```

---

## Verifikation dieses Teils

```bash
# Mit DEV_MODE=true und gültigem RSS_FEED_URL in .env:
python rss_sync.py
# Erwartete Ausgabe (erster Lauf): "RSS-Sync abgeschlossen: 10 neu, 0 beendet."

python rss_sync.py
# Erwartete Ausgabe (zweiter Lauf): "RSS-Sync abgeschlossen: 0 neu, 0 beendet."
```

Im `processed/`-Verzeichnis müssen JPEG-Dateien entstanden sein (je nach Feed-Inhalt
1–2 Seiten pro Eintrag).
