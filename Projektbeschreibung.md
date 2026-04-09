
Die Webanwendung solle folgende Funktionen haben:

- Anmeldung per OAuth2-Schnittstelle
- berechtigt sind Mitglieder der Gruppe _Infobildschirme_, alle anderen erhalten eine Fehlermeldung
- Berechtigte können Dateien in den Formaten .jpg, .png und .pdf hochladen
- Die Dateien werden skaliert und in das Format 3840 × 2160px eingepasst. Dabei darf das Bild nicht beschnitten werden.
- zu jedem hochgeladenen Bild tragen Benutzer einen Veröffentlichungsbeginn und -ende (Datum + Uhrzeit) ein.
- per Cronjob wird die Liste der hochgeladenen Dateien mit dem Inhalt eines entfernten Ordners über webdav verglichen:
	- Dateien, die im webdav-Ordner enthalten sind, aber nicht in der Liste werden aus dem webdav-Ordner gelöscht
	- Dateien, deren Veröffentlichungsdatum abgelaufen ist, werden aus dem webdav-Ordner gelöscht und in der Webanwendung ins Archiv verschoben
	- Dateien, deren Veröffentlichungsdatum noch nicht erreicht ist werden ignoriert
	- Dateien, deren Veröffentlichungsdatum erreicht ist und die im webdav-Ordner vorhanden sind, werden ignoriert
	- Dateien, deren Veröffentlichungsdatum erreicht ist und noch nicht im webdav-Ordner existieren, werden in den webdav-Ordner kopiert.
- Benutzer können Dateien im Archiv erneut veröffentlichen oder löschen