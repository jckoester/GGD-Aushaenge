# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a web application for managing digital signage content ("Aushaenge" = notice boards). The full requirements are in `Projektbeschreibung.md`.

## Implementierungsreihenfolge

1. Projektstruktur + FastAPI-Grundgerüst
2. Datenbankmodell + Datei-Upload
3. Bildverarbeitung (Skalierung auf 4K)
4. WebDAV-Sync + Cron-Job
5. Archiv-Funktionen
6. Veröffentlichungsdatum (Anfang und Ende bearbeiten)
7. dauerhafte Aushänge ohne Ablaufdatum
8. Frontend
9. OIDC-Login mit IServ + Gruppenprüfung
10. Optimierungen:
    - Löschen-Button für aktive Aushänge -> setzt Enddatum auf jetzt

Der OIDC-Login wird zuletzt implementiert, da für Tests eine Domain benötigt wird, die noch nicht verfügbar ist. Bis dahin ist die Anwendung ohne Authentifizierung zugänglich.

## Tech Stack

| Komponente | Technologie |
|---|---|
| Web-Framework | FastAPI + uvicorn |
| Reverse Proxy | nginx |
| Auth (OIDC) | Authlib – IServ als Provider, `groups`-Claim für Zugriffskontrolle |
| Bildverarbeitung | Pillow (JPEG/PNG), pdf2image + poppler-utils (PDF) |
| WebDAV-Client | webdavclient3 |
| Datenbank | SQLite via SQLAlchemy + Alembic (Migrationen) |
| Sync-Job | Systemcron (kein APScheduler) |

**System-Abhängigkeiten:** `poppler-utils` muss auf dem Server installiert sein (`apt install poppler-utils`).

## Core Requirements

**Authentication**
- OAuth2 login
- Only members of the group `Infobildschirme` may access the app; all others receive an error message

**File Management**
- Users can upload files in `.jpg`, `.png`, and `.pdf` formats
- Uploaded files are scaled and fitted into 3840×2160px (4K) without cropping
- Each uploaded file has a publication start and end date/time

**WebDAV Sync (Cronjob)**
The sync job compares the app's file list with a remote WebDAV folder:
- Files in WebDAV but not in the app's list → delete from WebDAV
- Files whose publication period has expired → delete from WebDAV, move to archive in the app
- Files whose publication period has not yet started → ignore
- Files whose publication period is active and already in WebDAV → ignore
- Files whose publication period is active but not yet in WebDAV → copy to WebDAV

**Archive**
- Users can re-publish or delete archived files
