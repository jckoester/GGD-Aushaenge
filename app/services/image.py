from pathlib import Path
from PIL import Image

TARGET_W, TARGET_H = 3840, 2160


def _letterbox(img: Image.Image) -> Image.Image:
    """Skaliert img maximal auf 4K-Canvas mit schwarzem Hintergrund, kein Crop."""
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
    img = img.convert("RGB")
    scale = min(TARGET_W / img.width, TARGET_H / img.height)
    new_w = round(img.width * scale)
    new_h = round(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x = (TARGET_W - new_w) // 2
    y = (TARGET_H - new_h) // 2
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
