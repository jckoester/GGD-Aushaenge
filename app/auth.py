from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings

oauth = OAuth()
_DEV_USER = {"name": "Dev User", "email": "dev@localhost"}
_oauth_registered = False


def get_oauth() -> OAuth:
    global _oauth_registered
    if not _oauth_registered:
        settings = get_settings()
        oauth.register(
            name="iserv",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            server_metadata_url=settings.oidc_server_metadata_url,
            client_kwargs={"scope": "openid profile email groups"},
        )
        _oauth_registered = True
    return oauth


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
