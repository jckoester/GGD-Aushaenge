from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_oauth, require_auth
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice
from app.routers import archive, files, sync, upload

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.processed_dir).mkdir(exist_ok=True)
    yield


app = FastAPI(title="GGD Aushaenge", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(upload.router)
app.include_router(archive.router)
app.include_router(sync.router)
app.include_router(files.router)


# ---------------------------------------------------------------------------
# Auth-Routen
# ---------------------------------------------------------------------------

@app.get("/login")
async def login(request: Request):
    oauth = get_oauth()
    redirect_uri = request.url_for("auth_callback")
    return await oauth.iserv.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    oauth = get_oauth()
    token = await oauth.iserv.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.iserv.userinfo(token=token)
    groups = userinfo.get("groups", {})
    group_acts = {g["act"] for g in groups.values() if isinstance(g, dict) and "act" in g}
    if settings.oidc_required_group not in group_acts:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "message": (
                    f'Kein Zugriff. Mitgliedschaft in der Gruppe '
                    f'"{settings.oidc_required_group}" erforderlich.'
                )
            },
            status_code=403,
        )
    request.session["user"] = {
        "name": userinfo.get("name") or userinfo.get("preferred_username", ""),
        "email": userinfo.get("email", ""),
    }
    return RedirectResponse(url="/")


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


# ---------------------------------------------------------------------------
# Seiten-Routen
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def page_index(request: Request, db: Session = Depends(get_db)):
    auth = require_auth(request)
    if isinstance(auth, RedirectResponse):
        return auth
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notices = (
        db.query(Notice)
        .filter(Notice.archived == False)
        .order_by(Notice.publish_start)
        .all()
    )
    return templates.TemplateResponse(
        request, "index.html", {"notices": notices, "now": now, "user": auth}
    )


@app.get("/archiv", response_class=HTMLResponse)
def page_archive(request: Request, db: Session = Depends(get_db)):
    auth = require_auth(request)
    if isinstance(auth, RedirectResponse):
        return auth
    notices = (
        db.query(Notice)
        .filter(Notice.archived == True)
        .order_by(Notice.publish_end.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "archive.html", {"notices": notices, "user": auth}
    )


@app.get("/health")
def health():
    return {"status": "ok"}
