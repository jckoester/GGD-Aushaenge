import uuid
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice
from app.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate
from app.services.image import process_upload

router = APIRouter(prefix="/upload", tags=["upload"])
settings = get_settings()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

@router.post("/", response_model=NoticeResponse, status_code=201)
async def upload_notice(
    file: UploadFile = File(...),
    publish_start: datetime = Form(...),
    publish_end: datetime = Form(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Dateityp '.{ext}' nicht erlaubt.")

    notice_data = NoticeCreate(publish_start=publish_start, publish_end=publish_end)

    stored_name = f"{uuid.uuid4()}.{ext}"
    dest = Path(settings.upload_dir) / stored_name

    contents = await file.read()
    dest.write_bytes(contents)

    file_type = "jpg" if ext == "jpeg" else ext
    db_notice = Notice(
        original_filename=file.filename,
        stored_filename=stored_name,
        file_type=file_type,
        publish_start=notice_data.publish_start,
        publish_end=notice_data.publish_end,
    )
    db.add(db_notice)
    db.commit()
    db.refresh(db_notice)

    try:
        base_name = Path(stored_name).stem
        page_count = process_upload(
            src=dest,
            dest_dir=Path(settings.processed_dir),
            base_name=base_name,
            file_type=file_type,
        )
    except Exception as e:
        db.delete(db_notice)
        db.commit()
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Bildverarbeitung fehlgeschlagen: {e}")

    db_notice.page_count = page_count
    db.commit()
    db.refresh(db_notice)
    return db_notice


@router.patch("/{notice_id}", response_model=NoticeResponse)
def update_notice_dates(
    notice_id: int,
    data: NoticeUpdate,
    db: Session = Depends(get_db),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    if notice.archived:
        raise HTTPException(status_code=400, detail="Archivierte Notices können nicht bearbeitet werden.")
    notice.publish_start = data.publish_start
    notice.publish_end = data.publish_end
    db.commit()
    db.refresh(notice)
    return notice


@router.get("/", response_model=list[NoticeResponse])
def list_notices(db: Session = Depends(get_db)):
    return (
        db.query(Notice)
        .filter(Notice.archived == False)
        .order_by(Notice.publish_start.desc())
        .all()
    )
