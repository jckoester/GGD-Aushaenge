# Step 11 / Teil 4: Integration – Schema, Editier-Sperre, Frontend

Voraussetzung: Teile 1–3 sind abgeschlossen und `rss_sync.py` läuft fehlerfrei.

---

## 1. Schema erweitern (`app/schemas/notice.py`)

`NoticeResponse` um die zwei neuen Felder ergänzen, damit das Frontend `source`
lesen kann (für den RSS-Badge) und API-Konsumenten `external_id` sehen:

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
    source: str = "user"            # NEU
    external_id: str | None = None  # NEU

    model_config = {"from_attributes": True}
```

Die Defaults (`"user"` bzw. `None`) stellen sicher, dass bestehende API-Clients
ohne Anpassung weiterarbeiten.

---

## 2. Editier-Sperre (`app/routers/upload.py`)

In `PATCH /{notice_id}` (Zeitraumbearbeitung) und `POST /{notice_id}/end`
(Beenden) jeweils **nach** der 404-Prüfung und **vor** der archived-Prüfung
einfügen:

```python
if notice.source == "rss":
    raise HTTPException(
        status_code=400,
        detail="RSS-Aushänge können nicht manuell bearbeitet werden."
    )
```

Beide Stellen: in `update_notice_dates` und in `end_notice`.

---

## 3. Republish-Sperre (`app/routers/archive.py`)

In `POST /{notice_id}/republish` **nach** der "nicht archiviert"-Prüfung ergänzen:

```python
if notice.source == "rss":
    raise HTTPException(
        status_code=400,
        detail="RSS-Aushänge können nicht erneut veröffentlicht werden."
    )
```

`DELETE /{notice_id}` bleibt **unverändert** — manuelles Löschen aus dem Archiv
ist erlaubt. `unlink(missing_ok=True)` deckt den fehlenden `.rss`-Dummy-Eintrag
bereits ab.

---

## 4. Frontend – Aktionsspalte (`app/templates/index.html`)

Den bisherigen `<td>` mit den Aktions-Buttons durch eine konditionierte Version
ersetzen. Die Zeile beginnt aktuell mit:

```html
<td>
    <button
        onclick="editNotice(
```

Ersetze den gesamten `<td>...</td>`-Block der Aktionsspalte durch:

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

---

## 5. CSS-Badge (`app/static/style.css`)

Am Ende der Datei (oder bei den anderen `.badge-*`-Klassen) ergänzen:

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

## Verifikation dieses Teils

1. App starten: `uvicorn app.main:app --reload`
2. Hauptseite aufrufen — RSS-Notices zeigen lila Badge „RSS / automatisch", keine Aktions-Buttons
3. Einen RSS-Aushang per API testen:
   ```bash
   curl -s -X PATCH http://localhost:8000/upload/<id> \
     -H "Content-Type: application/json" \
     -d '{"publish_start":"2026-01-01T00:00:00","publish_end":null}'
   # Erwartet: HTTP 400 "RSS-Aushänge können nicht manuell bearbeitet werden."
   ```
4. Archivseite prüfen — falls ein RSS-Eintrag archiviert wurde, erscheint kein „Erneut veröffentlichen"-Button (oder der Button wirft HTTP 400)
