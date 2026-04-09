from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice
from app.routers import upload, archive, sync, files

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.processed_dir).mkdir(exist_ok=True)
    yield

app = FastAPI(title="GGD Aushaenge", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(upload.router)
app.include_router(archive.router)
app.include_router(sync.router)
app.include_router(files.router)


@app.get("/", response_class=HTMLResponse)
def page_index(request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notices = (
        db.query(Notice)
        .filter(Notice.archived == False)
        .order_by(Notice.publish_start)
        .all()
    )
    return templates.TemplateResponse(
        request, "index.html", {"notices": notices, "now": now}
    )


@app.get("/archiv", response_class=HTMLResponse)
def page_archive(request: Request, db: Session = Depends(get_db)):
    notices = (
        db.query(Notice)
        .filter(Notice.archived == True)
        .order_by(Notice.publish_end.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "archive.html", {"notices": notices}
    )


@app.get("/health")
def health():
    return {"status": "ok"}