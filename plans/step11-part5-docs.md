# Step 11 / Teil 5: Dokumentation und Abschlussverifikation

Voraussetzung: Teile 1–4 sind vollständig abgeschlossen und lokal verifiziert.

---

## 1. README.md – Voraussetzungen

Im Abschnitt „Voraussetzungen" den Eintrag für `poppler-utils` erweitern:

```markdown
- `poppler-utils` und `fonts-dejavu-core` (für PDF-Verarbeitung und RSS-Rendering):
  `apt install poppler-utils fonts-dejavu-core`
```

---

## 2. README.md – Konfiguration

Im `.env`-Codeblock die neuen optionalen RSS-Variablen ergänzen:

```env
# RSS-Feed (optional)
RSS_FEED_URL=https://gymnasium-ditzingen.de/iserv/public/news/rss/1
RSS_ENABLED=true
```

---

## 3. README.md – Neuen Abschnitt „RSS-Feed-Sync" ergänzen

Nach dem bestehenden Abschnitt „Cron-Job einrichten" einen neuen Abschnitt
einfügen:

```markdown
## RSS-Feed-Sync einrichten

Der RSS-Sync liest den konfigurierten Feed und legt neue Nachrichten automatisch
als Aushänge an. Er läuft als eigenständiges Script mit eigenem Cron-Eintrag:

```bash
crontab -e
```

Folgenden Eintrag hinzufügen (Pfade anpassen):

```cron
*/15 * * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python rss_sync.py >> /var/log/ggd-rss.log 2>&1
```

Das Intervall (hier 15 Minuten) ist unabhängig vom WebDAV-Sync (5 Minuten).

Mit `RSS_ENABLED=false` in `.env` lässt sich der RSS-Sync deaktivieren, ohne
den Cron-Eintrag entfernen zu müssen.

### Was der RSS-Sync tut

- Einträge im Feed, die noch nicht in der DB sind → werden als Aushang angelegt
  und als 4K-Bild gerendert
- Einträge, die aus dem Feed verschwunden sind → bekommen `publish_end = jetzt`;
  der WebDAV-Sync archiviert sie beim nächsten Lauf
- Bereits bekannte Einträge → werden ignoriert (Duplikaterkennung via `guid`)

### Manuell ausführen

```bash
python rss_sync.py
```
```

---

## 4. Abschluss-Verifikation (vollständiger End-to-End-Test)

Alle Schritte mit `DEV_MODE=true` und laufender App durchführen:

### 4a – Migration
```bash
alembic upgrade head
# Muss fehlerfrei durchlaufen
```

### 4b – Erster RSS-Sync
```bash
python rss_sync.py
# Ausgabe: "RSS-Sync abgeschlossen: 10 neu, 0 beendet." (oder ähnlich)
```

### 4c – App starten und Seiten prüfen
```bash
uvicorn app.main:app --reload
```

- `http://localhost:8000/` → RSS-Aushänge erscheinen in der Liste mit lila Badge
  „RSS / automatisch", keine Zeitraum- oder Beenden-Buttons
- Vorschaubild klicken → gerendertes 4K-JPEG wird angezeigt
- Normaler Nutzer-Upload weiterhin möglich (Aktions-Buttons vorhanden)

### 4d – Editier-Sperre prüfen
```bash
# ID eines RSS-Aushangs aus der DB ermitteln:
curl http://localhost:8000/upload/ | python -m json.tool

# Zeitraum-Bearbeitung versuchen (erwartet HTTP 400):
curl -s -X PATCH http://localhost:8000/upload/<id> \
  -H "Content-Type: application/json" \
  -d '{"publish_start":"2026-01-01T00:00:00","publish_end":null}'

# Beenden versuchen (erwartet HTTP 400):
curl -s -X POST http://localhost:8000/upload/<id>/end
```

### 4e – Duplikaterkennung prüfen
```bash
python rss_sync.py
# Ausgabe: "RSS-Sync abgeschlossen: 0 neu, 0 beendet."
```

### 4f – WebDAV-Sync prüfen (falls WebDAV erreichbar)
```bash
python sync.py
# RSS-Aushänge mit aktivem Zeitraum werden in WebDAV hochgeladen
```

### 4g – Archiv-Flow prüfen (optional)
Einen RSS-Aushang manuell über die DB beenden (publish_end = jetzt), dann
`sync.py` ausführen → Aushang landet im Archiv. Im Archiv prüfen, dass
„Erneut veröffentlichen" einen Fehler liefert, „Löschen" aber funktioniert.
