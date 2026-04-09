from datetime import datetime
from pydantic import BaseModel, model_validator

class NoticeCreate(BaseModel):
    publish_start: datetime
    publish_end: datetime

    @model_validator(mode="after")
    def end_after_start(self) -> "NoticeCreate":
        if self.publish_end <= self.publish_start:
            raise ValueError("publish_end muss nach publish_start liegen")
        return self

class NoticeResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    file_type: str
    page_count: int
    publish_start: datetime
    publish_end: datetime
    archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}