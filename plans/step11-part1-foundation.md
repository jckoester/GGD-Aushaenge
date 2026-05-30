# Step 11 / Teil 1: Grundlage – Abhängigkeit, Modell, Migration, Konfiguration

Voraussetzung: keine. Dieser Teil muss als erstes umgesetzt werden; alle
weiteren Teile bauen darauf auf.

---

## 1. Abhängigkeit (`requirements.txt`)

`feedparser` ergänzen. Pinning wie alle anderen Pakete:

```bash
pip install feedparser
pip freeze | grep feedparser
```

Den ausgegebenen Versionseintrag (z. B. `feedparser==6.0.11`) in
`requirements.txt` einfügen — alphabetisch oder am Ende, konsistent mit dem
bestehenden Stil.

---

## 2. Datenmodell (`app/models/notice.py`)

Zwei neue Spalten in der `Notice`-Klasse ergänzen:

```python
source: Mapped[str] = mapped_column(String(10), default="user")
external_id: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
```

Der `String`-Import ist bereits vorhanden. Die Klasse danach:

```python
class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_type: Mapped[str] = mapped_column(String(10))
    publish_start: Mapped[datetime] = mapped_column(DateTime)
    publish_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    page_count: Mapped[int] = mapped_column(default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(10), default="user")           # NEU
    external_id: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)  # NEU
```

---

## 3. Alembic-Migration

Neue Datei in `migrations/versions/` anlegen. Dateinamen-Konvention der
vorhandenen Migrationen übernehmen (kurzer Hash + beschreibender Name).

`down_revision` muss auf `daa01a1e7b35` zeigen (letzte vorhandene Migration).

```python
"""add source and external_id to notices

Revision ID: <neuer hash>
Revises: daa01a1e7b35
Create Date: <aktuelles Datum>
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "<neuer hash>"
down_revision: Union[str, Sequence[str], None] = "daa01a1e7b35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(10), nullable=False, server_default="user")
        )
        batch_op.add_column(
            sa.Column("external_id", sa.String(512), nullable=True)
        )
        batch_op.create_unique_constraint("uq_notices_external_id", ["external_id"])


def downgrade() -> None:
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.drop_constraint("uq_notices_external_id", type_="unique")
        batch_op.drop_column("external_id")
        batch_op.drop_column("source")
```

Den Hash für `revision` mit `python -c "import uuid; print(uuid.uuid4().hex[:12])"` erzeugen.

Migration anschließend verifizieren:

```bash
alembic upgrade head
```

Fehlerfrei heißt: DB hat die Spalten `source` und `external_id` in der Tabelle
`notices`, alle bestehenden Zeilen haben `source = "user"`.

---

## 4. Konfiguration (`app/config.py`)

Zwei neue Felder in `Settings` ergänzen:

```python
rss_feed_url: str = "https://gymnasium-ditzingen.de/iserv/public/news/rss/1"
rss_enabled: bool = True
```

Beide Werte sind über `.env` überschreibbar (`RSS_FEED_URL`, `RSS_ENABLED`).
`rss_enabled = False` deaktiviert den Feed-Sync ohne Cron-Änderung.

---

## Verifikation dieses Teils

- `alembic upgrade head` läuft fehlerfrei durch
- `python -c "from app.models.notice import Notice; print(Notice.source, Notice.external_id)"` wirft keinen Fehler
- `python -c "from app.config import get_settings; s = get_settings(); print(s.rss_feed_url, s.rss_enabled)"` gibt die URL und `True` aus
