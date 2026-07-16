from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class HeartbeatPayload(BaseModel):
    device_id: str


class AIClassificationResult(BaseModel):
    device_id: str
    status: str
    reason: Optional[str] = None
    window_title: Optional[str] = None
    screenshot: Optional[str] = None
    confidence: Optional[float] = None
    activity: Optional[str] = None
    explanation: Optional[str] = None


class HeartbeatPayload(BaseModel):
    device_token: str


class MonitoringStateResponse(BaseModel):
    monitoring_active: bool
    active_sections: list[str]
    total_students: int
    studying_count: int
    off_task_count: int
    suspicious_count: int
    offline_count: int
