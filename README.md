# GGD Aushaenge

Webanwendung zur Verwaltung von digitalen Aushängen (Infoscreens).

## Cron-Job einrichten

Der Sync-Job gleicht die Datenbank mit dem WebDAV-Ordner ab. Er muss auf dem Server als Systemcron eingerichtet werden.

```bash
crontab -e
```

Folgenden Eintrag hinzufügen (Pfade anpassen):

```
*/5 * * * * cd /pfad/zum/projekt && /pfad/zum/venv/bin/python sync.py >> /var/log/ggd-sync.log 2>&1
```

Das Intervall (hier 5 Minuten) ist nach Bedarf anpassbar.

### Was der Sync-Job tut

- Dateien, die im WebDAV-Ordner liegen, aber keiner aktiven Notice zugeordnet sind → werden gelöscht
- Notices, deren Veröffentlichungszeitraum abgelaufen ist → werden archiviert
- Aktive Notices, deren Dateien noch nicht im WebDAV-Ordner liegen → werden hochgeladen

### Manuell ausführen

```bash
python sync.py
```

Oder über die API (nützlich für Tests):

```
POST /sync/run
```
