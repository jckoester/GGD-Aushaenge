from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_auth_dep
from app.config import get_settings
from app.database import get_db
from app.models.notice import Notice
from app.schemas.notice import NoticeCreate, NoticeResponse

router = APIRouter(prefix="/archive", tags=["archive"], dependencies=[Depends(require_auth_dep)])


@router.get("/", response_model=list[NoticeResponse])
def list_archive(db: Session = Depends(get_db)):
    return (
        db.query(Notice)
        .filter(Notice.archived == True)
        .order_by(Notice.publish_end.desc())
        .all()
    )


@router.post("/{notice_id}/republish", response_model=NoticeResponse)
def republish(
    notice_id: int,
    data: NoticeCreate,
    db: Session = Depends(get_db),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    if not notice.archived:
        raise HTTPException(status_code=400, detail="Notice ist nicht archiviert.")
    notice.archived = False
    notice.publish_start = data.publish_start
    notice.publish_end = data.publish_end
    db.commit()
    db.refresh(notice)
    return notice


@router.delete("/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db)):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="Notice nicht gefunden.")
    if not notice.archived:
        raise HTTPException(status_code=400, detail="Nur archivierte Notices können gelöscht werden.")

    settings = get_settings()
    base = Path(notice.stored_filename).stem

    Path(settings.upload_dir, notice.stored_filename).unlink(missing_ok=True)
    for i in range(1, notice.page_count + 1):
        Path(settings.processed_dir, f"{base}_p{i:03d}.jpg").unlink(missing_ok=True)

    db.delete(notice)
    db.commit()
