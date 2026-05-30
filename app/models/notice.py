from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_type: Mapped[str] = mapped_column(String(10))          # "jpg", "png", "pdf"
    publish_start: Mapped[datetime] = mapped_column(DateTime)
    publish_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    page_count: Mapped[int] = mapped_column(default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String(10), default="user")
    external_id: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)