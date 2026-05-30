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
    """Laedt alle <img>-Bilder aus der HTML-Description als PIL-Images."""
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
    """Gibt den Klartext der HTML-Description zurueck (HTML-Tags entfernt)."""
    if not description_html:
        return ""
    doc = lhtml.fromstring(description_html)
    return doc.text_content().strip()


def sync_feed(db: Session) -> tuple[int, int]:
    """
    Liest den RSS-Feed und gleicht ihn mit der DB ab:
    - Neue Eintraege -> Notice anlegen + rendern
    - Verschwundene Eintraege -> publish_end auf jetzt setzen

    Gibt (added, removed) zurueck.
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
            print(f"  Rendering fehlgeschlagen fuer '{title}': {e}")
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

    # Verschwundene Eintraege beenden (WebDAV-Sync archiviert sie dann automatisch)
    removed = 0
    now = datetime.utcnow()
    for ext_id, notice in existing.items():
        if ext_id not in feed_ids:
            notice.publish_end = now
            removed += 1

    db.commit()
    return added, removed
