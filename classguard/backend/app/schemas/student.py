from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class StudentCreate(BaseModel):
    name: str
    section: str


class StudentResponse(BaseModel):
    id: int
    name: str
    section: str
    unique_code: str
    connection_status: str
    last_seen: Optional[datetime] = None
    monitoring_enabled: bool
    monitoring_paused: bool
    pause_reason: Optional[str] = None
    current_status: str
    warning_count: int
    latest_screenshot: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LinkDeviceRequest(BaseModel):
    code: str


class LinkDeviceResponse(BaseModel):
    success: bool
    message: str
    device_token: Optional[str] = None
    student_name: Optional[str] = None
    section: Optional[str] = None
