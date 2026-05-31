from datetime import datetime
from pydantic import BaseModel, model_validator


class NoticeCreate(BaseModel):
    publish_start: datetime
    publish_end: datetime | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeCreate":
        if self.publish_end is not None and self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self


class NoticeUpdate(BaseModel):
    publish_start: datetime
    publish_end: datetime | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeUpdate":
        if self.publish_end is not None and self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self


class NoticeResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    file_type: str
    page_count: int
    publish_start: datetime
    publish_end: datetime | None
    archived: bool
    created_at: datetime
    source: str = "user"
    external_id: str | None = None

    model_config = {"from_attributes": True}
