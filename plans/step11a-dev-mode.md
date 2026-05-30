# Step 11a: Lokaler Entwicklungsmodus ohne OIDC-Login

## Ziel
Für die lokale Entwicklung (insbesondere Step 11 RSS-Feed) soll die App ohne
funktionierenden IServ-OIDC-Provider laufen. Ein neues Flag `dev_mode` schaltet
den Login-Zwang ab und injiziert einen synthetischen Testnutzer.

## Betroffene Dateien
- `app/config.py` — neues Setting `dev_mode`
- `app/auth.py` — Bypass in `require_auth` und `require_auth_dep`; `get_oauth()`
  bleibt unverändert (kein unnötiger Refactor)
- `app/main.py` — `/login`-Route erhält Dev-Mode-Zweig (kein OIDC-Redirect)
- `.env` (lokal, nicht eingecheckt) — `DEV_MODE=true` setzen

Keine weiteren Dateien müssen geändert werden. Die Router und Templates bekommen
den User bereits als Dict übergeben — das bleibt kompatibel.

---

## Schritt-für-Schritt-Anleitung für den Coding-Agent

### 1. `app/config.py` — Setting ergänzen

Füge `dev_mode: bool = False` zur `Settings`-Klasse hinzu. Der Default `False`
stellt sicher, dass das Produktionssystem ohne Änderung weiterläuft.

```python
class Settings(BaseSettings):
    secret_key: str
    database_url: str = "sqlite:///./ggd_aushaenge.db"
    upload_dir: str = "uploads"
    processed_dir: str = "processed"
    webdav_url: str
    webdav_user: str
    webdav_password: str
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_server_metadata_url: str = ""
    oidc_required_group: str = "Infobildschirme"
    dev_mode: bool = False          # NEU

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

### 2. `app/auth.py` — Bypass in `require_auth` und `require_auth_dep`

`get_oauth()` bleibt unangetastet — es wird nur aufgerufen, wenn tatsächlich
eine OAuth-Registrierung benötigt wird.

Ersetze die beiden `require_`-Funktionen:

```python
_DEV_USER = {"name": "Dev User", "email": "dev@localhost"}


def require_auth(request: Request):
    """Für HTML-Routen: leitet zu /login um, falls nicht eingeloggt."""
    if get_settings().dev_mode:
        return _DEV_USER
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    return user


def require_auth_dep(request: Request):
    """Für API-Router: wirft HTTP 401, falls nicht eingeloggt."""
    if get_settings().dev_mode:
        return
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Nicht eingeloggt.")
```

Der Import von `get_settings` ist in `auth.py` bereits vorhanden (kommt über
`app.config`). Falls nicht, hinzufügen.

### 3. `app/main.py` — `/login`-Route absichern

Im Dev-Mode darf `/login` nicht versuchen, einen OIDC-Redirect auszuführen
(der Provider ist nicht erreichbar). Stattdessen: synthetischen User in die
Session schreiben und direkt auf `/` weiterleiten.

Ersetze die `/login`-Route:

```python
@app.get("/login")
async def login(request: Request):
    if settings.dev_mode:
        request.session["user"] = {"name": "Dev User", "email": "dev@localhost"}
        return RedirectResponse(url="/")
    oauth = get_oauth()
    redirect_uri = request.url_for("auth_callback")
    return await oauth.iserv.authorize_redirect(request, redirect_uri)
```

`/auth/callback` und `/logout` bleiben unverändert. Im Dev-Mode wird `/login`
nie echte OAuth-Calls auslösen, also spielt der Callback keine Rolle.

### 4. `.env` lokal anpassen

Füge in der lokalen `.env`-Datei (nicht einchecken!) hinzu:

```
DEV_MODE=true
```

Die OIDC-Variablen (`OIDC_CLIENT_ID` etc.) können leer bleiben oder ganz
weggelassen werden — sie werden im Dev-Mode nie ausgewertet.

Ebenso können `WEBDAV_URL`, `WEBDAV_USER`, `WEBDAV_PASSWORD` auf Dummy-Werte
gesetzt werden, falls kein lokaler WebDAV-Server verfügbar ist:

```
WEBDAV_URL=http://localhost:5005/
WEBDAV_USER=dev
WEBDAV_PASSWORD=dev
```

### 5. Verifikation

Nach den Änderungen:
1. `uvicorn app.main:app --reload` starten
2. `http://localhost:8000/` aufrufen → direkt Hauptseite (kein Login-Redirect)
3. `http://localhost:8000/login` aufrufen → sofort Redirect auf `/`
4. Upload, Archiv und alle anderen Routen testen — sie erhalten `_DEV_USER` als
   `user`-Variable und funktionieren wie im Produktionsmodus

## Sicherheitshinweis

`dev_mode=True` darf **niemals** in `.env` auf dem Produktionsserver gesetzt
werden. Es gibt keinen weiteren Schutz. Das Flag ist ausschließlich für die
lokale Entwicklungsumgebung gedacht. Die `settings`-Objekte sind gecacht
(`@lru_cache`) — ein Neustart ist nötig, um das Flag zu ändern.

## Abgrenzung

Dieser Plan ändert **kein** Produktionsverhalten und **keine** Geschäftslogik.
Er ist eine rein additive Ergänzung als Voraussetzung für Step 11 (RSS-Feed),
der eine laufende lokale App ohne Domain/IServ-Zugang benötigt.
