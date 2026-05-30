# Step 11 / Teil 2: Rendering – Font-Helper und `render_news()`

Voraussetzung: Teil 1 ist abgeschlossen (Modell und Config vorhanden).

Alle Änderungen in diesem Teil betreffen ausschließlich
`app/services/image.py`. Die bestehenden Funktionen (`_letterbox`,
`process_raster`, `process_pdf`, `process_upload`) bleiben **unverändert**.

---

## 1. Font-Ressource vorbereiten

Verzeichnis `app/fonts/` anlegen und eine `.gitkeep`-Datei hineinstellen
(damit das leere Verzeichnis ins Repo eingecheckt werden kann).

Im README und in der Serverdokumentation `fonts-dejavu-core` als neue
System-Voraussetzung ergänzen:

```
apt install poppler-utils fonts-dejavu-core
```

Alternativ kann man die Fontdateien manuell nach `app/fonts/` kopieren:
- `DejaVuSans.ttf`
- `DejaVuSans-Bold.ttf`

---

## 2. Neue Imports in `app/services/image.py`

Am Anfang der Datei ergänzen:

```python
from PIL import ImageDraw, ImageFont
```

(Der `Image`-Import ist bereits vorhanden.)

---

## 3. Konstanten

Direkt nach den bestehenden Konstanten (`TARGET_W`, `TARGET_H`) einfügen:

```python
_BG_COLOR    = (20, 30, 48)       # Dunkles Nachtblau
_TITLE_COLOR = (255, 255, 255)
_TEXT_COLOR  = (200, 210, 220)
_PAD         = 240                # Innenabstand in Pixeln
```

---

## 4. `_find_font(bold=False) -> Path`

```python
def _find_font(bold: bool = False) -> Path:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        Path(__file__).parent.parent / "fonts" / name,
        Path(f"/usr/share/fonts/truetype/dejavu/{name}"),
        Path(f"/usr/share/fonts/dejavu/{name}"),
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"{name} nicht gefunden. Bitte 'apt install fonts-dejavu-core' "
        "ausführen oder Fonts nach app/fonts/ kopieren."
    )
```

---

## 5. `_wrap_lines(text, font, max_width) -> list[str]`

```python
def _wrap_lines(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
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

---

## 6. `_draw_text_block(canvas, title, body, area_box)`

Rendert Titel und Fließtext in eine Bounding-Box `(x0, y0, x1, y1)`.

```python
def _draw_text_block(
    canvas: Image.Image,
    title: str,
    body: str,
    area_box: tuple[int, int, int, int],
) -> None:
    x0, y0, x1, y1 = area_box
    area_w = x1 - x0
    draw = ImageDraw.Draw(canvas)

    title_font = ImageFont.truetype(str(_find_font(bold=True)), size=110)
    body_font  = ImageFont.truetype(str(_find_font(bold=False)), size=68)

    max_w = area_w - 2 * _PAD
    y = y0 + _PAD

    # Titel
    for line in _wrap_lines(title, title_font, max_w):
        draw.text((x0 + _PAD, y), line, font=title_font, fill=_TITLE_COLOR)
        y += 130

    # Abstand zwischen Titel und Body
    if body.strip():
        y += 60
        for line in _wrap_lines(body, body_font, max_w):
            draw.text((x0 + _PAD, y), line, font=body_font, fill=_TEXT_COLOR)
            y += 85
```

---

## 7. Seiten-Render-Hilfsfunktionen

### `_page_text_only`

```python
def _page_text_only(title: str, body: str) -> Image.Image:
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), _BG_COLOR)
    _draw_text_block(canvas, title, body, (0, 0, TARGET_W, TARGET_H))
    return canvas
```

### `_page_image_only`

```python
def _page_image_only(img: Image.Image) -> Image.Image:
    return _letterbox(img)
```

### `_page_landscape_split` (Bild oben 60 %, Text unten 40 %)

```python
def _page_landscape_split(img: Image.Image, title: str, body: str) -> Image.Image:
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), _BG_COLOR)
    split_y = int(TARGET_H * 0.60)   # 1296 px

    # Bild in Subcanvas (3840 × split_y) letterboxen
    sub = Image.new("RGB", (TARGET_W, split_y), (0, 0, 0))
    img_rgb = img.convert("RGB")
    scale = min(TARGET_W / img_rgb.width, split_y / img_rgb.height)
    new_w = round(img_rgb.width * scale)
    new_h = round(img_rgb.height * scale)
    img_resized = img_rgb.resize((new_w, new_h), Image.LANCZOS)
    sub.paste(img_resized, ((TARGET_W - new_w) // 2, (split_y - new_h) // 2))
    canvas.paste(sub, (0, 0))

    # Text unten
    _draw_text_block(canvas, title, body, (0, split_y, TARGET_W, TARGET_H))
    return canvas
```

### `_page_portrait_split` (Text links 50 %, Bild rechts 50 %)

```python
def _page_portrait_split(img: Image.Image, title: str, body: str) -> Image.Image:
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), _BG_COLOR)
    split_x = TARGET_W // 2   # 1920 px

    # Text links
    _draw_text_block(canvas, title, body, (0, 0, split_x, TARGET_H))

    # Bild in Subcanvas (1920 × 2160) letterboxen
    sub = Image.new("RGB", (split_x, TARGET_H), (0, 0, 0))
    img_rgb = img.convert("RGB")
    scale = min(split_x / img_rgb.width, TARGET_H / img_rgb.height)
    new_w = round(img_rgb.width * scale)
    new_h = round(img_rgb.height * scale)
    img_resized = img_rgb.resize((new_w, new_h), Image.LANCZOS)
    sub.paste(img_resized, ((split_x - new_w) // 2, (TARGET_H - new_h) // 2))
    canvas.paste(sub, (split_x, 0))

    return canvas
```

---

## 8. Hauptfunktion `render_news()`

```python
def render_news(
    title: str,
    body_text: str,
    images: list,
    dest_dir: Path,
    base_name: str,
) -> int:
    """Rendert einen RSS-News-Eintrag als 4K-JPEG(s). Gibt page_count zurück."""
    has_body = bool(body_text.strip())
    n = len(images)
    pages: list[Image.Image] = []

    if n == 0:
        pages.append(_page_text_only(title, body_text))
    elif n == 1 and not has_body:
        pages.append(_page_image_only(images[0]))
    elif n == 1:
        img = images[0]
        if img.width > img.height:
            pages.append(_page_landscape_split(img, title, body_text))
        else:
            pages.append(_page_portrait_split(img, title, body_text))
    else:
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

## Verifikation dieses Teils

Schnelltest ohne laufende App (fonts-dejavu-core oder Fonts in app/fonts/ vorausgesetzt):

```python
from pathlib import Path
from PIL import Image
from app.services.image import render_news

dest = Path("processed")
dest.mkdir(exist_ok=True)

# Text-only
n = render_news("Testtitel", "Das ist ein Testtext.", [], dest, "test_text")
assert n == 1

# Bild-only (Querformat)
img_quer = Image.new("RGB", (1920, 1080), (100, 150, 200))
n = render_news("Nur Bild", "", [img_quer], dest, "test_img_quer")
assert n == 1

# Text + Querformat-Bild
n = render_news("Titel", "Fließtext hier.", [img_quer], dest, "test_split_quer")
assert n == 1

# Text + Hochformat-Bild
img_hoch = Image.new("RGB", (1080, 1920), (200, 100, 150))
n = render_news("Titel", "Fließtext hier.", [img_hoch], dest, "test_split_hoch")
assert n == 1

# Mehrere Bilder + Text → 3 Seiten (1 Text + 2 Bilder)
n = render_news("Titel", "Text.", [img_quer, img_hoch], dest, "test_multi")
assert n == 3

print("Alle Rendering-Tests bestanden.")
```

Alle erzeugten JPEGs müssen 3840×2160 px groß sein.
