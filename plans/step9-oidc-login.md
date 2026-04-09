# Plan: Schritt 9 – OIDC-Login mit IServ

## Ziel

Alle Routen der Anwendung werden durch OIDC-Login geschützt. Als Provider dient IServ.
Nur Mitglieder der Gruppe `Infobildschirme` erhalten Zugang; alle anderen sehen eine Fehlerseite.
Nicht eingeloggte Benutzer werden automatisch zum IServ-Login weitergeleitet.

---

## Abhängigkeiten

`itsdangerous` fehlt noch (wird von `SessionMiddleware` benötigt):

```bash
pip install itsdangerous
pip freeze > requirements.txt
```

Bereits vorhanden: `authlib`, `httpx`.

---

## Konfiguration (`.env`)

Drei neue Pflichtfelder (Platzhalter im `.env.example` ergänzen):

```
OIDC_CLIENT_ID=ggd-aushaenge
OIDC_CLIENT_SECRET=<secret>
OIDC_SERVER_METADATA_URL=https://<iserv-domain>/.well-known/openid-configuration
SECRET_KEY=<zufälliger langer String für Session-Signierung>
```

`OIDC_REQUIRED_GROUP` ist bereits in `Settings` vorhanden (Default: `Infobildschirme`).

---

## `app/auth.py` (neu)

Enthält:

1. **Authlib-OAuth-Client** – einmaliges Registrieren des IServ-Providers:

```python
from authlib.integrations.starlette_client import OAuth
from app.config import get_settings

oauth = OAuth()

def get_oauth():
    settings = get_settings()
    oauth.register(
        name="iserv",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        server_metadata_url=settings.oidc_server_metadata_url,
        client_kwargs={"scope": "openid profile email groups"},
    )
    return oauth
```

2. **`require_auth(request)`** – FastAPI-Dependency, die auf jeder geschützten Route verwendet wird:

```python
from fastapi import Request
from fastapi.responses import RedirectResponse

def require_auth(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(...)  # wird als RedirectResponse zur /login-Route
    return user
```

Konkret: wirft keine HTTPException, sondern gibt eine `RedirectResponse` zurück – daher als Dependency mit `response_model=None` oder als direkte Funktion, die im Router aufgerufen wird (siehe unten).

**Empfohlenes Muster:** `require_auth` als einfache Hilfsfunktion (kein Depends), die in jedem Route-Handler direkt aufgerufen wird:

```python
def get_current_user(request: Request):
    """Gibt den eingeloggten User zurück oder None."""
    return request.session.get("user")

def require_auth(request: Request):
    """Leitet zur Login-Seite um, falls nicht eingeloggt. Gibt User zurück."""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    return user
```

Da FastAPI keine `RedirectResponse` aus einem Depends heraus transparent weiterleitet, wird `require_auth` **nicht** als `Depends` eingebunden, sondern am Anfang jedes Route-Handlers aufgerufen:

```python
@app.get("/")
def page_index(request: Request, db: Session = Depends(get_db)):
    auth = require_auth(request)
    if isinstance(auth, RedirectResponse):
        return auth
    # auth ist jetzt das user-Dict
    ...
```

---

## Login-/Callback-Routen (`app/main.py`)

```python
@app.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth_callback")
    return await oauth.iserv.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    token = await oauth.iserv.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.iserv.userinfo(token=token)
    settings = get_settings()
    groups = userinfo.get("groups", [])
    if settings.oidc_required_group not in groups:
        return templates.TemplateResponse(request, "error.html", {
            "message": f"Kein Zugriff. Mitgliedschaft in der Gruppe „{settings.oidc_required_group}" erforderlich."
        }, status_code=403)
    request.session["user"] = {
        "name": userinfo.get("name", userinfo.get("preferred_username", "")),
        "email": userinfo.get("email", ""),
    }
    return RedirectResponse(url="/")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")
```

---

## `SessionMiddleware` in `app/main.py`

```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
```

Muss **vor** `app.mount` und `app.include_router` hinzugefügt werden (Middleware wird in umgekehrter Reihenfolge angewendet).

---

## Geschützte Routen

Alle bestehenden Routen in `main.py` und allen Routern werden geschützt. Vorgehen:

- **`main.py`** (`GET /`, `GET /archiv`): `require_auth`-Aufruf direkt am Anfang des Handlers
- **Router** (`upload`, `archive`, `files`, `sync`): Gemeinsame Dependency via `Depends`:

```python
from app.auth import require_auth_dep

router = APIRouter(
    prefix="/upload",
    tags=["upload"],
    dependencies=[Depends(require_auth_dep)],
)
```

Für API-Router (JSON-Antworten) ist eine separate Dependency `require_auth_dep` sinnvoll, die bei fehlendem Login **HTTP 401** zurückgibt statt einer Redirect-Response:

```python
def require_auth_dep(request: Request):
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Nicht eingeloggt.")
```

---

## `app/templates/error.html` (neu)

Einfache Fehlerseite, extends `base.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="error-box">
    <h1>Zugriff verweigert</h1>
    <p>{{ message }}</p>
    <a href="/logout">Abmelden</a>
</div>
{% endblock %}
```

---

## Benutzername in der Navigation

Den eingeloggten Benutzernamen in `base.html` anzeigen. `user` wird allen Template-Responses mitgegeben:

```python
# In main.py, page_index und page_archive:
user = require_auth(request)
...
return templates.TemplateResponse(request, "index.html", {"notices": notices, "now": now, "user": user})
```

In `base.html`:
```html
{% if user %}
<span class="nav-user"><i data-lucide="user"></i> {{ user.name }}</span>
<a href="/logout" class="nav-btn"><i data-lucide="log-out"></i> Abmelden</a>
{% endif %}
```

---

## Reihenfolge der Umsetzung

1. `itsdangerous` installieren, `requirements.txt` aktualisieren
2. `app/auth.py` anlegen
3. `SessionMiddleware` + OAuth-Initialisierung in `main.py`
4. Login/Callback/Logout-Routen in `main.py`
5. `error.html` anlegen
6. `require_auth` in `main.py`-Routen einbauen
7. `require_auth_dep` in allen API-Routern als Router-Dependency einbauen

---

## Verifikation

1. `GET /` ohne Session → Redirect zu `/login`
2. `/login` leitet zu IServ weiter
3. Nach erfolgreichem Login mit Gruppenmitglied → Redirect zu `/`, Session gesetzt
4. Login mit Benutzer ohne Gruppe → `error.html` mit 403
5. `GET /logout` → Session gelöscht, Redirect zu `/login`
6. API-Endpunkt ohne Session → HTTP 401
7. Benutzername erscheint in der Navigation
