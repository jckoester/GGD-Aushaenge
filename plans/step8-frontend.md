# Plan: Schritt 8 – Frontend

## Ziel

Zwei HTML-Seiten mit Jinja2-Templates. Tabellenbasiertes Layout, kein CSS-Framework. Flatpickr für Datums-/Zeiteingaben (15-min-Raster). Modales Overlay für Datumseingaben. Minimales JavaScript (nur Flatpickr + Modal + fetch-Aufrufe).

---

## Abhängigkeiten

Flatpickr wird lokal ausgeliefert (Datenschutz – kein CDN). Die drei Dateien vor der Umsetzung herunterladen und in `app/static/vendor/` ablegen:

```
app/static/vendor/
├── flatpickr.min.css
├── flatpickr.min.js
└── de.js
```

Download-Befehle:

```bash
mkdir -p app/static/vendor
curl -Lo app/static/vendor/flatpickr.min.css https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css
curl -Lo app/static/vendor/flatpickr.min.js https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.js
curl -Lo app/static/vendor/de.js https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/de.js
```

Einbindung in `base.html`:

```html
<link rel="stylesheet" href="/static/vendor/flatpickr.min.css">
<script src="/static/vendor/flatpickr.min.js"></script>
<script src="/static/vendor/de.js"></script>
```

---

## Verzeichnisstruktur

```
app/
├── templates/
│   ├── base.html
│   ├── index.html
│   └── archive.html
└── static/
    └── style.css
```

---

## FastAPI-Seitenrouten (`app/main.py`)

Zwei neue GET-Routen, die HTML zurückgeben. Beide übergeben `now` (naive UTC datetime) an den Template-Kontext für die Statusberechnung im Template.

```python
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def page_index(request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notices = (
        db.query(Notice)
        .filter(Notice.archived == False)
        .order_by(Notice.publish_start)
        .all()
    )
    return templates.TemplateResponse(
        "index.html", {"request": request, "notices": notices, "now": now}
    )

@app.get("/archiv", response_class=HTMLResponse)
def page_archive(request: Request, db: Session = Depends(get_db)):
    notices = (
        db.query(Notice)
        .filter(Notice.archived == True)
        .order_by(Notice.publish_end.desc())
        .all()
    )
    return templates.TemplateResponse(
        "archive.html", {"request": request, "notices": notices}
    )
```

`Notice` und `get_db` müssen in `main.py` importiert werden.

---

## `app/templates/base.html`

Minimales HTML5-Layout:
- `<head>`: charset, viewport, title, `style.css`, Flatpickr CSS+JS (CDN)
- `<nav>`: zwei Links – „Aushänge" (`/`) und „Archiv" (`/archiv`)
- `<main>`: Block `content`
- Am Ende `<div id="modal">` für das modale Overlay (immer im DOM, per CSS ein-/ausgeblendet)
- `<script>`-Block am Ende für gemeinsames JS (Modal-Logik, Flatpickr-Init, API-Hilfsfunktionen)

---

## `app/templates/index.html`

Extends `base.html`. Überschrift „Aktive Aushänge".

### Tabellenspalten

| Vorschau | Dateiname | Zeitraum | Status | Aktionen |
|---|---|---|---|---|

**Status** wird im Template berechnet:
- `publish_start > now` → „geplant"
- `publish_start <= now` und (`publish_end is None` oder `publish_end > now`) → „aktiv"

### Erste Zeile: Upload-Formular

Kein Vorschaubild – stattdessen ein `<input type="file" accept=".jpg,.jpeg,.png,.pdf">`.
- Flatpickr-Input für `publish_start` (Pflichtfeld)
- Flatpickr-Input für `publish_end` + Checkbox „dauerhaft" (blendet den Input aus)
- Button „Anlegen" rechts

Submit per JavaScript (`fetch POST /upload/` als `multipart/form-data`), bei Erfolg Seite neu laden.

### Weitere Zeilen: eine pro Notice

- Vorschaubild: `<img src="/files/{id}/preview">` (CSS: 80px Breite, Seitenverhältnis erhalten)
- Dateiname (original), Dateityp, Seitenanzahl
- Zeitraum: formatiertes `publish_start` – `publish_end` (oder „dauerhaft")
- Status-Badge
- Aktionen:
  - Button „Zeitraum bearbeiten" → öffnet Modal (s. u.) mit aktuellem `publish_start`/`publish_end` vorausgefüllt; schickt `PATCH /upload/{id}`
  - Button „Beenden" → `fetch PATCH /upload/{id}` mit `publish_end = jetzt` (ISO-String), bei Erfolg Seite neu laden. `onclick="return confirm('Aushang jetzt beenden?')"` als Schutz vor Versehen.

---

## `app/templates/archive.html`

Extends `base.html`. Überschrift „Archiv".

### Tabellenspalten

| Vorschau | Dateiname | Typ | War aktiv | Aktionen |
|---|---|---|---|---|

### Zeilen

- Vorschaubild wie in View 1
- „War aktiv": `publish_start` – `publish_end` (oder „dauerhaft")
- Aktionen:
  - Button „Erneut veröffentlichen" → öffnet Modal; schickt `POST /archive/{id}/republish`
  - Button „Löschen" → `fetch DELETE /archive/{id}`, bei Erfolg Zeile aus DOM entfernen. `onclick="return confirm(...)"` als Schutz.

---

## Modales Overlay

Ein einzelnes Modal im DOM (in `base.html`), das von beiden Views genutzt wird.

**Aufbau:**
```html
<div id="modal" class="modal-backdrop hidden">
  <div class="modal-box">
    <h2 id="modal-title"></h2>
    <label>Start</label>
    <input id="modal-start" type="text">
    <label>Ende</label>
    <input id="modal-end" type="text">
    <label><input id="modal-permanent" type="checkbox"> Dauerhaft</label>
    <div class="modal-actions">
      <button id="modal-cancel">Abbrechen</button>
      <button id="modal-submit">Speichern</button>
    </div>
  </div>
</div>
```

**JS-Logik:**

```javascript
function openModal(title, startIso, endIso, onSubmit) {
    // Titel setzen, Flatpickr-Werte vorausfüllen, onSubmit-Callback speichern
    // Modal einblenden
}
// modal-submit: onSubmit-Callback aufrufen mit den aktuellen Werten
// modal-cancel: Modal ausblenden
// modal-permanent checkbox: end-Input und dessen Label ein-/ausblenden
```

Flatpickr-Konfiguration für beide Modal-Inputs:
```javascript
flatpickr("#modal-start", {
    enableTime: true,
    time_24hr: true,
    minuteIncrement: 15,
    locale: "de",
    dateFormat: "Y-m-dTH:i:S",  // ISO für API
    altInput: true,
    altFormat: "d.m.Y H:i",     // Anzeige für Nutzer
});
```

---

## `app/static/style.css`

- Basis: `box-sizing: border-box`, serifenlose Schrift, heller Hintergrund
- `nav`: horizontale Leiste, Links mit Abstand
- `table`: volle Breite, `border-collapse: collapse`, Zeilen mit dünner Trennlinie
- `td img`: `width: 80px; height: auto;`
- Status-Badges: farbige `<span>` (grün = aktiv, gelb = geplant)
- Modal-Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.5)`; `.hidden { display: none }`
- Modal-Box: zentriert, weiß, `border-radius`, Padding, `max-width: 400px`
- Responsive: ab `max-width: 768px` Tabellenspalten „Typ" und „Seiten" ausblenden

---

## Reihenfolge der Umsetzung

Da beide Views auf demselben Fundament aufbauen, empfiehlt sich:

1. `base.html` + `style.css` + Modal-JS + FastAPI-Routen in `main.py`
2. `index.html` (View 1)
3. `archive.html` (View 2)

---

## Verifikation

1. `GET /` rendert die Tabelle mit Upload-Zeile und allen nicht-archivierten Notices
2. Upload über die Tabellen-Zeile legt eine neue Notice an und lädt die Seite neu
3. „Zeitraum bearbeiten" öffnet das Modal vorausgefüllt, PATCH wird korrekt abgeschickt
4. „Beenden" setzt `publish_end` auf jetzt nach Bestätigung
5. „Dauerhaft"-Checkbox blendet Enddatum aus und schickt `publish_end: null`
6. `GET /archiv` zeigt alle archivierten Notices
7. „Erneut veröffentlichen" öffnet Modal, POST wird abgeschickt, Notice verschwindet aus Archiv
8. „Löschen" entfernt die Zeile nach Bestätigung
9. Vorschaubilder werden korrekt geladen
10. Auf iPad (768px) sind die Spalten „Typ" lesbar oder ausgeblendet
