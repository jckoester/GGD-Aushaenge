# Plan: Schritt 6 – Veröffentlichungsdatum bearbeiten

## Ziel

Benutzer können `publish_start` und `publish_end` einer bestehenden, nicht archivierten Notice nachträglich ändern. Dazu kommt ein neuer PATCH-Endpunkt in den Upload-Router. Keine Datenbankmigrationen nötig – das Modell ändert sich nicht.

---

## Neues Schema: `NoticeUpdate`

### `app/schemas/notice.py` – `NoticeUpdate` ergänzen

```python
class NoticeUpdate(BaseModel):
    publish_start: datetime
    publish_end: datetime

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeUpdate":
        if self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self
```

`NoticeUpdate` ist inhaltlich identisch mit `NoticeCreate`. Es wird als eigener Typ angelegt, damit die Semantik klar ist und spätere Erweiterungen (z. B. optionale Felder) unabhängig voneinander möglich sind.

---

## Neuer Endpunkt: `PATCH /upload/{notice_id}`

### `app/routers/upload.py` – Endpunkt ergänzen

```python
from app.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate

@router.patch("/{notice_id}", response_model=NoticeResponse)
def update_notice_dates(
    notice_id: int,
    data: NoticeUpdate,
    db: Session = Depends(get_db),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    if notice.archived:
        raise HTTPException(status_code=400, detail="Archivierte Notices können nicht bearbeitet werden.")
    notice.publish_start = data.publish_start
    notice.publish_end = data.publish_end
    db.commit()
    db.refresh(notice)
    return notice
```

**Hinweise:**
- Nur nicht-archivierte Notices können bearbeitet werden. Für archivierte gibt es bereits `POST /archive/{id}/republish`.
- Der Endpunkt ändert ausschließlich die Datumsfelder – keine Dateioperationen nötig.
- HTTP 400 bei archivierten Notices (statt 404), damit der Client unterscheiden kann, ob die Notice existiert oder gesperrt ist.

---

## Verifikation

Der Schritt gilt als abgeschlossen, wenn:

1. `PATCH /upload/{id}` mit gültigem Zeitraum aktualisiert `publish_start` und `publish_end` und gibt die Notice zurück
2. `PATCH /upload/{id}` mit `publish_end <= publish_start` gibt HTTP 422 zurück
3. `PATCH /upload/{id}` mit unbekannter ID gibt HTTP 404 zurück
4. `PATCH /upload/{id}` auf eine archivierte Notice gibt HTTP 400 zurück
