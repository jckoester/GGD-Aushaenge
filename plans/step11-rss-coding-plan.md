# Step 11: RSS-Feed-News als automatische Aushänge – Coding-Plan

## Kontext

Der IServ-RSS-Feed `https://gymnasium-ditzingen.de/iserv/public/news/rss/1` liefert
Items in dieser Struktur:

```xml
<item>
  <title><![CDATA[Woche der iPad-Nutzung]]></title>
  <description><![CDATA[
    <p><img src="https://gymnasium-ditzingen.de/news/images/251/6919c7dd9bde15.16031963_Display_wdiN_4k.png"
            width="640" height="360" alt="..." /></p>
    <p>Optionaler Fließtext hier.</p>
  ]]></description>
  <guid><![CDATA[https://gymnasium-ditzingen.de/iserv/public/news/rss/1#251]]></guid>
  <pubDate>Sun, 16 Nov 2025 13:47:00 +0100</pubDate>
  <category><![CDATA[1]]></category>
</item>
```

Wichtige Erkenntnisse:
- Bilder liegen **nur** als `<img src>` in der `<description>` (kein `<enclosure>`,
  kein `<media:content>`)
- `<title>` und `<guid>` sind immer CDATA-umschlossen
- `feedparser` entpackt CDATA automatisch
- Der Fließtext kann fehlen; dann besteht die Description nur aus dem `<img>`-Tag
- Kein Schullogo im Rendering nötig

## Designentscheidungen (vom Nutzer bestätigt)

| Situation | Layout |
|---|---|
| Nur Bild (kein Fließtext) | Bild letterboxed, kein Titel-Overlay |
| Nur Text (kein Bild) | Volles 4K-Textlayout: Titel oben, Text darunter |
| Text + 1 Bild, Querformat (w > h) | Bild oben 60 %, Titel + Text unten 40 % |
| Text + 1 Bild, Hochformat (h ≥ w) | Bild rechts (50 %), Titel + Text links (50 %) |
| Mehrere Bilder + Text | Seite 1 = Text, Seiten 2..N = je ein Bild letterboxed |
| Mehrere Bilder, kein Text | Seiten 1..N = je ein Bild letterboxed |

RSS-Notices laufen **dauerhaft** (`publish_end=None`) solange sie im Feed stehen.
Ein eigenes Script `rss_sync.py` mit eigenem Cron-Eintrag steuert den Feed-Abgleich.

---

## Schritt 1 – Abhängigkeit ergänzen (`requirements.txt`)

Füge `feedparser` hinzu. Die exakte Version ermitteln mit
`pip install feedparser && pip freeze | grep feedparser` oder einfach ohne
Pinning, wenn alle anderen bereits gepinnt sind. Akzeptabel ist auch
`feedparser>=6.0`.

---

## Schritt 2 – Datenmodell (`app/models/notice.py`)

Zwei neue Spalten in der `Notice`-Klasse ergänzen:

```python
source: Mapped[str] = mapped_column(String(10), default="user")
external_id: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
```

`source` unterscheidet `"user"` (Upload) von `"rss"` (Feed-Eintrag).
`external_id` enthält den `guid`-Wert des Feed-Eintrags (z. B.
`https://gymnasium-ditzingen.de/iserv/public/news/rss/1#251`) und ist `UNIQUE`,
damit Duplikate beim erneuten Lauf sofort erkannt werden.

---

## Schritt 3 – Alembic-Migration

Neue Migrationsdatei in `migrations/versions/` anlegen (Namensschema analog zu den
vorhandenen). Pflichtmuster: `op.batch_alter_table` (SQLite-kompatibel).

```python
def upgrade() -> None:
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(10), nullable=False, server_default="user"))
        batch_op.add_column(sa.Column("external_id", sa.String(512), nullable=True))
        batch_op.create_unique_constraint("uq_notices_external_id", ["external_id"])

def downgrade() -> None:
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.drop_constraint("uq_notices_external_id", type_="unique")
        batch_op.drop_column("external_id")
        batch_op.drop_column("source")
```

`down_revision` muss auf `daa01a1e7b35` zeigen (letzte vorhandene Migration).

---

## Schritt 4 – Konfiguration (`app/config.py`)

Ergänze in der `Settings`-Klasse:

```python
rss_feed_url: str = "https://gymnasium-ditzingen.de/iserv/public/news/rss/1"
rss_enabled: bool = True
```

Beide Werte aus `.env` überschreibbar (`RSS_FEED_URL`, `RSS_ENABLED`).

---

## Schritt 5 – Font-Ressource

Das Textrendering benötigt TrueType-Schriften. Definiere in
`app/services/image.py` eine Hilfsfunktion `_find_font(bold=False) -> Path`, die
folgende Pfade in Reihenfolge prüft und den ersten gefundenen zurückgibt:

```
app/fonts/DejaVuSans-Bold.ttf   (lokale Kopie, bold)
app/fonts/DejaVuSans.ttf        (lokale Kopie, regular)
/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf
/usr/share/fonts/dejavu/DejaVuSans.ttf
```

Wenn kein Font gefunden wird, `FileNotFoundError` mit der Meldung
`"DejaVuSans nicht gefunden. Bitte 'apt install fonts-dejavu-core' ausführen oder Fonts nach app/fonts/ kopieren."`.

Das Verzeichnis `app/fonts/` anlegen (leer, per `.gitkeep`). Im README und in der
Systemd-Doku ergänzen: `apt install fonts-dejavu-core` als Server-Voraussetzung.

---

## Schritt 6 – Rendering (`app/services/image.py` erweitern)

Füge folgende Funktionen zu `app/services/image.py` hinzu. Die bestehenden
Funktionen (`_letterbox`, `process_raster`, `process_pdf`, `process_upload`)
bleiben **unverändert**.

### 6a – Hilfsfunktionen

```python
_BG_COLOR = (20, 30, 48)       # Dunkles Nachtblau
_TITLE_COLOR = (255, 255, 255)
_TEXT_COLOR = (200, 210, 220)
_PAD = 240                     # Innenabstand in Pixeln
```

**`_find_font(bold=False) -> Path`** — wie in Schritt 5 beschrieben.

**`_wrap_lines(text: str, font, max_width: int) -> list[str]`** — bricht Text in
Zeilen mit maximalem Pixel-Breite. Wörter-basierter Umbruch:

```python
def _wrap_lines(text, font, max_width):
    words = text.split()
    lines, current = [], []
    for word in words:
        probe = " ".join(current + [word])
        if font.getlength(probe) > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines
```

**`_draw_text_block(canvas, title, body, area_box, draw)`** — rendert Titel und
Fließtext in eine Bounding-Box `(x0, y0, x1, y1)`:

- Lädt `_find_font(bold=True)` für Titel (Größe 110 px) und `_find_font()` für
  Body (Größe 68 px) via `ImageFont.truetype(str(font_path), size)`
- Titel-Zeilen: `_wrap_lines(title, title_font, area_width - 2*_PAD)`, gezeichnet
  ab `(x0 + _PAD, y0 + _PAD)` mit `line_height = 130`
- Body-Zeilen: `_wrap_lines(body, body_font, area_width - 2*_PAD)`, gezeichnet
  direkt unter dem Titel mit `line_height = 85` und einem Abstand von 60 px
- Hintergrund der area_box wird **nicht** separat gefüllt — das erledigt der
  Aufrufer

### 6b – Seiten-Render-Funktionen

**`_page_text_only(title, body) -> Image`**: 3840×2160-Canvas mit `_BG_COLOR`,
ruft `_draw_text_block` für den gesamten Canvas auf.

**`_page_image_only(img) -> Image`**: Gibt `_letterbox(img)` zurück.

**`_page_landscape_split(img, title, body) -> Image`**:
- Canvas 3840×2160, komplett `_BG_COLOR`
- Bildzone: y=0 bis y=1296 (60 %), Breite 3840 → `_letterbox`-ähnlich in
  3840×1296 einfügen (erstellt eigenen Sub-Canvas, dann in Haupt-Canvas paste)
- Textzone: `(0, 1296, 3840, 2160)` → `_draw_text_block`

**`_page_portrait_split(img, title, body) -> Image`**:
- Canvas 3840×2160, komplett `_BG_COLOR`
- Textzone links: `(0, 0, 1920, 2160)` → `_draw_text_block`
- Bildzone rechts: Bild in 1920×2160 letterboxen und bei x=1920 einfügen

### 6c – Hauptfunktion

```python
def render_news(
    title: str,
    body_text: str,
    images: list,           # list[PIL.Image.Image]
    dest_dir: Path,
    base_name: str,
) -> int:
    """Rendert einen RSS-News-Eintrag als 4K-JPEG(s). Gibt page_count zurück."""
    pages: list[Image.Image] = []
    has_body = bool(body_text.strip())
    n = len(images)

    if n == 0:
        # Nur Text
        pages.append(_page_text_only(title, body_text))
    elif n == 1 and not has_body:
        # Nur Bild
        pages.append(_page_image_only(images[0]))
    elif n == 1:
        # Text + 1 Bild: Layout nach Seitenverhältnis
        img = images[0]
        if img.width > img.height:          # Querformat
            pages.append(_page_landscape_split(img, title, body_text))
        else:                               # Hochformat
            pages.append(_page_portrait_split(img, title, body_text))
    else:
        # Mehrere Bilder
        if has_body:
            pages.append(_page_text_only(title, body_text))
        for img in images:
            pages.append(_page_image_only(img))

    for i, page in enumerate(pages, start=1):
        out = dest_dir / f"{base_name}_p{i:03d}.jpg"
        page.save(out, "JPEG", quality=92)

    return len(pages)
```

---

## Schritt 7 – RSS-Service (`app/services/rss.py`, neu)

```python
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import mktime
from urllib.parse import urljoin

import feedparser
import requests
from lxml import html as lhtml
from PIL import Image
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.notice import Notice
from app.services.image import render_news


def _extract_images(description_html: str, base_url: str) -> list:
    """Lädt alle <img>-Bilder aus der HTML-Description."""
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
    """Gibt den Klartext der HTML-Description zurück."""
    if not description_html:
        return ""
    doc = lhtml.fromstring(description_html)
    return doc.text_content().strip()


def sync_feed(db: Session) -> tuple[int, int]:
    """
    Liest den RSS-Feed, legt neue Notices an und beendet verschwundene.
    Gibt (added, removed) zurück.
    """
    settings = get_settings()
    if not settings.rss_enabled:
        return 0, 0

    feed = feedparser.parse(settings.rss_feed_url)

    # Basis-URL für relative Bild-Pfade (Feed-Domain)
    from urllib.parse import urlparse
    parsed = urlparse(settings.rss_feed_url)
    feed_base = f"{parsed.scheme}://{parsed.netloc}/"

    # Bestehende RSS-Notices aus DB (aktiv, nicht archiviert)
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

        # Veröffentlichungsdatum
        published = entry.get("published_parsed")
        if published:
            pub_dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc).replace(tzinfo=None)
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

    # Verschwundene Einträge beenden (Sync archiviert sie danach)
    removed = 0
    now = datetime.utcnow()
    for ext_id, notice in existing.items():
        if ext_id not in feed_ids:
            notice.publish_end = now
            removed += 1

    db.commit()
    return added, removed
```

---

## Schritt 8 – RSS-Sync-Script (`rss_sync.py`, Projektroot)

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

## Schritt 9 – Schema erweitern (`app/schemas/notice.py`)

`NoticeResponse` um die neuen Felder ergänzen, damit das Frontend sie lesen kann:

```python
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
    source: str = "user"           # NEU
    external_id: str | None = None # NEU

    model_config = {"from_attributes": True}
```

---

## Schritt 10 – Editier-Sperre in Routen

### `app/routers/upload.py`

In `PATCH /{notice_id}` (Zeitraumbearbeitung) und `POST /{notice_id}/end` (Beenden)
jeweils **nach** der 404-Prüfung ergänzen:

```python
if notice.source == "rss":
    raise HTTPException(status_code=400, detail="RSS-Aushänge können nicht manuell bearbeitet werden.")
```

### `app/routers/archive.py`

In `POST /{notice_id}/republish` **nach** der "nicht archiviert"-Prüfung ergänzen:

```python
if notice.source == "rss":
    raise HTTPException(status_code=400, detail="RSS-Aushänge können nicht erneut veröffentlicht werden.")
```

`DELETE /{notice_id}` bleibt unverändert — manuelles Löschen aus dem Archiv ist
erlaubt (der Feed steuert die Neuanlage).

**Wichtig:** In `DELETE /{notice_id}` versucht der Code, `upload_dir/stored_filename`
zu löschen. Bei RSS-Notices existiert diese Datei nicht (`.rss` ist synthetisch).
Das ist kein Problem, weil `unlink(missing_ok=True)` verwendet wird — kein Fix nötig.

---

## Schritt 11 – Frontend (`app/templates/index.html`)

In der Notice-Tabellenschleife (`{% for n in notices %}`) die Aktionsspalte
konditionieren. Ersetze den bisherigen `<td>` mit den Buttons durch:

```html
<td>
    {% if n.source == "rss" %}
        <span class="badge badge-rss">RSS / automatisch</span>
    {% else %}
        <button
            onclick="editNotice(
                {{ n.id }},
                '{{ n.publish_start.isoformat() }}',
                {{ ('\''+n.publish_end.isoformat()+'\'') if n.publish_end else 'null' }}
            )"><i data-lucide="pencil"></i> Zeitraum</button>
        <button
            class="btn-danger btn-space-top"
            onclick="endNotice({{ n.id }})"><i data-lucide="square"></i> Beenden</button>
    {% endif %}
</td>
```

Außerdem in der CSS-Datei (`app/static/style.css`) eine neue Badge-Klasse ergänzen:

```css
.badge-rss {
    background: #7c3aed;
    color: #fff;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    white-space: nowrap;
}
```

---

## Schritt 12 – Cron-Eintrag (Dokumentation in README.md)

Im README-Abschnitt „Cron-Job einrichten" einen zweiten Eintrag ergänzen:

```cron
*/15 * * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python rss_sync.py >> /var/log/ggd-rss.log 2>&1
```

Intervall: 15 Minuten (unabhängig vom 5-Minuten-WebDAV-Sync).
Mit `RSS_ENABLED=false` in `.env` lässt sich der Job ohne Cron-Änderung
deaktivieren.

Außerdem: `fonts-dejavu-core` zu den Server-Voraussetzungen ergänzen:

```
apt install poppler-utils fonts-dejavu-core
```

---

## Schritt 13 – Verifikation (lokal mit DEV_MODE=true)

1. `alembic upgrade head` ausführen — prüfen, ob die DB-Migration sauber läuft
2. `python rss_sync.py` einmalig ausführen — Ausgabe muss `X neu, 0 beendet` zeigen
3. App starten, Hauptseite aufrufen — RSS-Notices erscheinen mit Badge „RSS / automatisch"
4. Zeitraum-Button bei RSS-Notice klicken → Fehlermeldung vom Server erwartet
5. Beenden-Button bei RSS-Notice klicken → Fehlermeldung erwartet
6. `python rss_sync.py` erneut ausführen → `0 neu, 0 beendet` (Duplikaterkennung)

---

## Reihenfolge der Implementierung (empfohlen)

1. Schritt 1 (requirements), 2 (Modell), 3 (Migration), 4 (Config) — Grundlage
2. Schritt 5 (Font-Helper), 6 (render_news) — Rendering, isoliert testbar
3. Schritt 7 (rss.py), 8 (rss_sync.py) — Service und Script
4. Schritt 9 (Schema), 10 (Editier-Sperre), 11 (Frontend) — Integration
5. Schritt 12 (Doku), 13 (Verifikation) — Abschluss
