from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from app.config import get_settings
from app.routers import upload, archive, sync, files

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.processed_dir).mkdir(exist_ok=True)
    yield

app = FastAPI(title="GGD Aushaenge", lifespan=lifespan)

app.include_router(upload.router)
app.include_router(archive.router)
app.include_router(sync.router)
app.include_router(files.router)

@app.get("/health")
def health():
    return {"status": "ok"}