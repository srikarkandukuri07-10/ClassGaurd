from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.config import settings
from app.models.student import Student
from app.models.device import Device
from app.models.warning import Warning as WarningModel
from app.models.monitoring_log import MonitoringLog
from app.schemas.monitoring import AIClassificationResult
from app.ws.manager import manager
import os
import base64
import uuid

from pydantic import BaseModel
from typing import Optional
import httpx

from app.core.classifier import ScreenClassifier

router = APIRouter(prefix="/api/ai", tags=["ai"])
classifier = ScreenClassifier()


class ClassifyRequest(BaseModel):
    device_id: str
    window_title: Optional[str] = None
    image: Optional[str] = None


@router.post("/classify")
async def classify_agent_request(req: ClassifyRequest):
    result = await classifier.classify(
        image_b64=req.image,
        window_title=req.window_title,
    )
    return result


@router.post("/result")
async def handle_ai_classification(
    body: AIClassificationResult,
    db: AsyncSession = Depends(get_db),
):
    device_result = await db.execute(
        select(Device).where(
            Device.device_token == body.device_id,
            Device.status == "active",
        )
    )
    device = device_result.scalar_one_or_none()
    if not device:
        return {"error": "Device not found"}

    student_result = await db.execute(select(Student).where(Student.id == device.student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        return {"error": "Student not found"}

    if not student.monitoring_enabled or student.monitoring_paused:
        return {"message": "Monitoring disabled for this student"}

    now = datetime.now(timezone.utc)
    student.last_seen = now
    device.last_seen = now
    student.connection_status = "connected"

    old_status = student.current_status
    student.current_status = body.status

    # Decode and save screenshot
    screenshot_url = None
    if body.screenshot:
        try:
            static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "static"))
            os.makedirs(os.path.join(static_dir, "screenshots"), exist_ok=True)
            
            # Remove base64 header if present
            img_b64 = body.screenshot
            if "," in img_b64:
                img_b64 = img_b64.split(",")[1]
                
            image_data = base64.b64decode(img_b64)
            filename = f"{uuid.uuid4()}.jpg"
            filepath = os.path.join(static_dir, "screenshots", filename)
            with open(filepath, "wb") as f:
                f.write(image_data)
            screenshot_url = f"/static/screenshots/{filename}"
        except Exception as e:
            print("Failed to save screenshot:", e)

    # Save monitoring log history
    log = MonitoringLog(
        student_id=student.id,
        status=body.status,
        confidence=body.confidence or (0.95 if body.status in ("off-task", "suspicious") else 0.8),
        reason=body.reason or body.window_title or "Monitoring",
        window_title=body.window_title or "",
        screenshot_path=screenshot_url,
    )
    db.add(log)
    if screenshot_url:
        student.latest_screenshot = screenshot_url

    if body.status == "off-task":
        now_ts = now.timestamp()
        last_warned = getattr(student, 'last_warned_at', None)
        secs_since = (now_ts - last_warned.timestamp()) if last_warned else 999

        # Only increment warning count if at least 60 seconds have passed
        if secs_since >= 60:
            student.warning_count += 1
            if hasattr(student, 'last_warned_at'):
                student.last_warned_at = now

            warning = WarningModel(
                student_id=student.id,
                level=student.warning_count,
                reason=body.reason or body.window_title or "",
            )
            db.add(warning)

        warning_messages = {
            1: "You appear to be off-task. Please return to your studies.",
            2: "Second warning. Please return to class activities.",
            3: "Final warning. Faculty has been notified.",
        }

        msg = warning_messages.get(
            student.warning_count,
            f"Warning #{student.warning_count}. Faculty has been notified.",
        )

        await manager.send_to_agent(student.unique_code, "warning", {
            "level": min(student.warning_count, 3),
            "message": msg,
            "reason": body.reason,
        })

        # Broadcast live notification for off-task behavior to staff
        await manager.broadcast_faculty("faculty_notification", {
            "type": "off-task",
            "student_id": student.id,
            "student_name": student.name,
            "section": student.section,
            "reason": body.reason or "Browsing unauthorized applications",
            "confidence": int((body.confidence or 0.95) * 100),
            "screenshot": screenshot_url,
            "time": datetime.now(timezone.utc).strftime("%I:%M %p"),
            "warning_count": student.warning_count,
        })
    elif body.status == "suspicious":
        # Broadcast live notification for suspicious behavior to staff
        await manager.broadcast_faculty("faculty_notification", {
            "type": "suspicious",
            "student_id": student.id,
            "student_name": student.name,
            "section": student.section,
            "reason": body.reason or "Suspicious activity detected",
            "confidence": int((body.confidence or 0.8) * 100),
            "screenshot": screenshot_url,
            "time": datetime.now(timezone.utc).strftime("%I:%M %p"),
            "warning_count": student.warning_count,
        })

    # Broadcast updated student status to faculty dashboard
    await manager.broadcast_faculty("student_status", {
        "student_id": student.id,
        "name": student.name,
        "section": student.section,
        "status": body.status,
        "reason": body.reason or body.window_title or "",
        "warning_count": student.warning_count,
        "screenshot": screenshot_url,
        "last_seen": now.isoformat(),
    })

    await db.commit()
    return {"ok": True}
