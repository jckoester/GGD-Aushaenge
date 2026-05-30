# Step 11: RSS-Feed-News als automatische Aushänge

## Ziel
Die Software soll wichtige News aus einem RSS-Feed (z. B.
`https://gymnasium-ditzingen.de/iserv/public/news/rss/1`) automatisch als
4K-Bildaushänge in den bestehenden Veröffentlichungsflow einschleusen:

- Feed regelmäßig einlesen
- neue News als 4K-Bilder (3840×2160) rendern – **inklusive der im News-Beitrag
  enthaltenen Bilder**
- diese Aushänge in den regulären Flow einschleusen, aber **nicht durch Nutzer
  bearbeitbar**
- Aushänge zu News, die nicht mehr im Feed stehen, automatisch entfernen

## Konzept
RSS-News werden als spezielle `Notice` mit `source="rss"` behandelt. Damit laufen
sie automatisch durch den bestehenden Sync-/WebDAV-Flow. Sie sind dauerhaft
(`publish_end=None`), solange sie im Feed stehen, und werden beendet, sobald sie
verschwinden. Ein eigener Schritt liest den Feed; der WebDAV-Sync bleibt unverändert.

## Umsetzung

### 1. Datenmodell (`app/models/notice.py` + Alembic-Migration)
Zwei neue Spalten auf `Notice`:
- `source: str` — `"user"` (Default) oder `"rss"`
- `external_id: str | None` — stabile Feed-ID (`guid` bzw. Link), `unique`, zur
  Duplikaterkennung

Neue Migration analog zu den vorhandenen (`migrations/versions/`), per
`op.batch_alter_table` (SQLite-kompatibel).

### 2. Konfiguration (`app/config.py`)
Neue Settings: `rss_feed_url` (die genannte URL), optional `rss_enabled: bool` und
`rss_image_dir` für zwischengespeicherte Feed-Bilder. Werte aus `.env`.

### 3. RSS-Service (`app/services/rss.py`, neu)
- Feed per `feedparser` einlesen (neue Abhängigkeit in `requirements.txt`).
- Pro `<item>`: Titel, Text und **Bild** extrahieren. Bildquelle robust in dieser
  Reihenfolge: `media:content`/`media:thumbnail` → `<enclosure>` → erstes
  `<img src>` in der HTML-`description`. HTML-Tags für den Text via `lxml`
  (bereits vorhanden) entfernen.
- Bild herunterladen (über `requests`, bereits vorhanden) — **mit Bestätigung des
  Nutzers**, da Downloads von externer Quelle bestätigungspflichtig sind. Relative
  URLs gegen die Feed-Basis-URL auflösen.
- Diff gegen DB: neue `external_id` → Notice anlegen + rendern; verschwundene
  RSS-News → `publish_end = jetzt` setzen (der bestehende Sync archiviert/löscht
  sie dann).

> **Annahme** mangels Live-Zugriff auf den Feed: Bilder liegen als `<img>` in der
> `description` oder als `enclosure`/`media`. Beim ersten echten Lauf die
> tatsächliche Struktur prüfen und das Parsing minimal justieren. Ggf. ein
> Beispiel-`<item>` aus dem Feed besorgen.

### 4. News-Rendering (`app/services/image.py`, erweitern)
Neue Funktion `render_news(...)` → eine 4K-JPEG-Datei (3840×2160) nach dem
bestehenden Namensschema `{base}_p001.jpg`, damit Sync und Vorschau ohne
Sonderfall funktionieren:
- Layout mit Pillow: Hintergrund, Schullogo, Titel (groß), Fließtext mit
  automatischem Zeilenumbruch.
- **Feed-Bild** wird per `_letterbox`-ähnlicher Logik in einen definierten
  Bildbereich eingepasst (kein Crop), z. B. obere oder rechte Hälfte; Text füllt
  den Rest.
- Fallback ohne Bild: reines Text-Layout.
- TrueType-Schrift nötig (z. B. DejaVuSans, im System vorhanden) — sonst eine
  Schrift mitliefern.

### 5. Sync-Integration (`sync.py`)
Vor dem WebDAV-Abgleich `rss.sync_feed()` aufrufen (oder als separater Cronjob, je
nach gewünschtem Intervall). Der WebDAV-Teil bleibt komplett unverändert.

### 6. Editier-Sperre (nicht durch Nutzer bearbeitbar)
- `app/routers/upload.py`: in `PATCH /{id}` und `/{id}/end` für `source=="rss"`
  eine `HTTPException` werfen (analog zur `archived`-Prüfung).
- `app/templates/index.html`: bei RSS-Zeilen Aktions-Buttons ausblenden,
  stattdessen Badge „RSS / automatisch".
- `app/routers/archive.py`: republish/delete für RSS-News optional sperren oder
  erlauben. Vorschlag: löschen erlauben, republish nicht, da der Feed steuert.

### 7. Tests (`tests/`)
- Feed-Parsing mit gemocktem Feed-XML (inkl. Bild-Varianten).
- Diff-Logik: neue/verschwundene News.
- Rendering: erzeugt 3840×2160-JPEG mit und ohne Bild.

## Offene Fragen / vor Umsetzung zu klären
1. **Bild-Download-Freigabe**: Das Herunterladen der Feed-Bilder ist ein externer
   Download — dafür wird ein OK benötigt (einmalig generell für den Feed).
2. **Layout-Wunsch**: Bild oben + Text unten, oder Bild links/rechts? Soll das
   Schullogo immer eingeblendet werden?
3. **Intervall**: gleicher Takt wie der WebDAV-Sync oder eigener Cronjob
   (z. B. alle 15 Min)?
4. **Feed-Beispiel**: Falls möglich ein Beispiel-`<item>` aus dem Feed, um das
   Bild-Parsing direkt richtig zu treffen.

## Hinweis zur Reihenfolge
Folgt nach den bestehenden Schritten 1–10. Der OIDC-Login (Step 9) ist davon
unabhängig.
