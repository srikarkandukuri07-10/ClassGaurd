from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DisableRequestCreate(BaseModel):
    device_id: str
    reason: str


class DisableResponse(BaseModel):
    message: str
    request_id: int


class DisableRequestResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    section: str
    reason: str
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DisableRequestAction(BaseModel):
    request_id: int
    action: str
