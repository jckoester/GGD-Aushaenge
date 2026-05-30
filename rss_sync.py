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
