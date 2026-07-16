from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import os
import base64
import uuid
import asyncio
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db, async_session
from app.core.config import settings
from app.models.student import Student
from app.models.device import Device
from app.models.warning import Warning as WarningModel
from app.models.monitoring_log import MonitoringLog
from app.schemas.monitoring import AIClassificationResult
from app.ws.manager import manager
from app.core.classifier import ScreenClassifier

router = APIRouter(prefix="/api/ai", tags=["ai"])
classifier = ScreenClassifier()


class ClassifyRequest(BaseModel):
    device_id: str
    window_title: Optional[str] = None
    image: Optional[str] = None


async def process_student_frame(device_id: str, window_title: Optional[str], image_b64: Optional[str]):
    print(f"\n[AI Observer Task] Starting background check for device: {device_id}, window: '{window_title}'")
    
    async with async_session() as db:
        # 1. Resolve Device and Student
        device_result = await db.execute(
            select(Device).where(
                Device.device_token == device_id,
                Device.status == "active",
            )
        )
        device = device_result.scalar_one_or_none()
        if not device:
            print(f"[AI Observer Task] Device not found for token: {device_id}")
            return
            
        student_result = await db.execute(
            select(Student).where(Student.id == device.student_id)
        )
        student = student_result.scalar_one_or_none()
        if not student:
            print(f"[AI Observer Task] Student not found for ID: {device.student_id}")
            return
            
        if not student.monitoring_enabled or student.monitoring_paused:
            print(f"[AI Observer Task] Monitoring inactive/paused for: {student.name}")
            return

        now = datetime.now(timezone.utc)
        
        # 2. Check if we need to throttle AI Vision model calls
        # We only run classification if the window title has changed, OR if 5 seconds have passed since the last log.
        # This keeps the system responsive and protects Gemini API key from rate limits.
        last_log_query = await db.execute(
            select(MonitoringLog)
            .where(MonitoringLog.student_id == student.id)
            .order_by(MonitoringLog.created_at.desc())
            .limit(1)
        )
        last_log = last_log_query.scalar_one_or_none()
        
        time_elapsed = 999.0
        if last_log and last_log.created_at:
            last_created = last_log.created_at
            if last_created.tzinfo is None:
                last_created = last_created.replace(tzinfo=timezone.utc)
            time_elapsed = (now - last_created).total_seconds()
            
        title_changed = last_log is None or last_log.window_title != window_title
        
        run_ai = title_changed or time_elapsed >= 5.0
        
        if not run_ai:
            # Skip Vision call to optimize API quota; connection updates are already processed
            print(f"[AI Observer Task] Throttled. Skipping vision run. (Title changed: {title_changed}, elapsed: {time_elapsed:.1f}s)")
            return
            
        print(f"[AI Observer Task] Classifying window: '{window_title}'. (Title changed: {title_changed}, elapsed: {time_elapsed:.1f}s)")
        result = await classifier.classify(
            image_b64=image_b64,
            window_title=window_title
        )
        
        status = result.get("status", "studying")
        confidence = result.get("confidence", 0.9)
        activity = result.get("activity", "Active Activity")
        reason = result.get("reason", "")
        explanation = result.get("explanation", "")
        
        # 3. Update status in memory
        student.last_seen = now
        device.last_seen = now
        student.connection_status = "connected"
        student.current_status = status
        
        # 4. Determine if we should save screenshot to disk (off-task/suspicious or every 15 seconds)
        screenshot_url = student.latest_screenshot
        should_save_to_disk = status in ("off-task", "suspicious")
        if not should_save_to_disk and image_b64:
            if not student.last_seen or (now - student.last_seen.replace(tzinfo=timezone.utc)).total_seconds() >= 15.0:
                should_save_to_disk = True
                
        if should_save_to_disk and image_b64:
            try:
                static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "static"))
                os.makedirs(os.path.join(static_dir, "screenshots"), exist_ok=True)
                img_b64 = image_b64
                if "," in img_b64:
                    img_b64 = img_b64.split(",")[1]
                image_data = base64.b64decode(img_b64)
                filename = f"{uuid.uuid4()}.jpg"
                filepath = os.path.join(static_dir, "screenshots", filename)
                with open(filepath, "wb") as f:
                    f.write(image_data)
                screenshot_url = f"/static/screenshots/{filename}"
                student.latest_screenshot = screenshot_url
            except Exception as e:
                print(f"[AI Observer Task] Failed to save screenshot: {e}")

        # 5. Create monitoring log entry
        log = MonitoringLog(
            student_id=student.id,
            status=status,
            confidence=confidence,
            reason=reason or window_title or "Monitoring",
            window_title=window_title or "",
            screenshot_path=screenshot_url,
            activity=activity,
            explanation=explanation,
        )
        db.add(log)
        
        # 6. Warning System: increment on OFF_TASK, reset on STUDYING
        if status == "off-task":
            student.warning_count += 1
            
            warning = WarningModel(
                student_id=student.id,
                level=student.warning_count,
                reason=activity,
            )
            db.add(warning)
            
            # Wording per requirements:
            # 1. "You appear to be off-task. Please return to your studies."
            # 2. "Second warning. Please return to class activities."
            # 3. "Final warning. Faculty has been notified."
            warning_messages = {
                1: "You appear to be off-task. Please return to your studies.",
                2: "Second warning. Please return to class activities.",
                3: "Final warning. Faculty has been notified.",
            }
            msg = warning_messages.get(
                student.warning_count,
                "Final warning. Faculty has been notified."
            )
            
            # Send warning to student agent via WebSocket
            print(f"[AI Observer Task] Sending Warning Level {student.warning_count} to {student.name}")
            await manager.send_to_agent(student.unique_code, "warning", {
                "level": student.warning_count,
                "message": msg,
                "reason": activity,
            })
            
            # Send notification to faculty dashboard (websocket)
            print(f"[AI Observer Task] Broadcasting Faculty Alert for {student.name}")
            await manager.broadcast_faculty("faculty_notification", {
                "type": "off-task",
                "student_id": student.id,
                "student_name": student.name,
                "section": student.section,
                "activity": activity,
                "reason": reason,
                "explanation": explanation,
                "confidence": int(confidence * 100),
                "screenshot": screenshot_url,
                "time": now.strftime("%I:%M %p"),
                "warning_count": student.warning_count,
            })
            
        elif status == "suspicious":
            # Notify faculty for suspicious actions
            print(f"[AI Observer Task] Broadcasting Suspicious Alert for {student.name}")
            await manager.broadcast_faculty("faculty_notification", {
                "type": "suspicious",
                "student_id": student.id,
                "student_name": student.name,
                "section": student.section,
                "activity": activity,
                "reason": reason,
                "explanation": explanation,
                "confidence": int(confidence * 100),
                "screenshot": screenshot_url,
                "time": now.strftime("%I:%M %p"),
                "warning_count": student.warning_count,
            })
            
        elif status == "studying":
            # Reset warnings if STUDYING is detected again!
            if student.warning_count > 0:
                print(f"[AI Observer Task] Resetting warnings to 0 for {student.name} (returned to studying)")
                student.warning_count = 0
                
        # 7. Always broadcast student status update to faculty dashboard
        await manager.broadcast_faculty("student_status", {
            "student_id": student.id,
            "name": student.name,
            "section": student.section,
            "status": status,
            "activity": activity,
            "reason": reason,
            "explanation": explanation,
            "warning_count": student.warning_count,
            "screenshot": screenshot_url,
            "last_seen": now.isoformat(),
        })
        
        await db.commit()
        print(f"[AI Observer Task] Completed task successfully for {student.name}")


@router.post("/classify")
async def classify_agent_request(req: ClassifyRequest, db: AsyncSession = Depends(get_db)):
    print(f"\n[HTTP Classify] Frame received from device: {req.device_id}, window: '{req.window_title}'")
    
    device_result = await db.execute(
        select(Device).where(
            Device.device_token == req.device_id,
            Device.status == "active",
        )
    )
    device = device_result.scalar_one_or_none()
    if not device:
        print("[HTTP Classify] Device not found")
        return {"error": "Device not found"}
        
    student_result = await db.execute(
        select(Student).where(Student.id == device.student_id)
    )
    student = student_result.scalar_one_or_none()
    if not student:
        print("[HTTP Classify] Student not found")
        return {"error": "Student not found"}

    now = datetime.now(timezone.utc)
    student.last_seen = now
    device.last_seen = now
    student.connection_status = "connected"
    
    # 1. Immediately broadcast the live frame to the faculty dashboard (WebSocket)
    # This provides the real-time screen share view!
    if req.image:
        await manager.broadcast_faculty("live_frame", {
            "student_id": student.id,
            "screenshot": req.image,
            "window_title": req.window_title or "",
        })
        
    # 2. Schedule the AI classification asynchronously
    asyncio.create_task(process_student_frame(req.device_id, req.window_title, req.image))
    
    await db.commit()
    # 3. Return immediately to keep the agent responsive
    return {"ok": True}


@router.post("/result")
async def handle_ai_classification(
    body: AIClassificationResult,
    db: AsyncSession = Depends(get_db),
):
    """Fallback endpoint — forward to process task for backward compatibility if needed"""
    asyncio.create_task(process_student_frame(body.device_id, body.window_title, body.screenshot))
    return {"ok": True}


@router.post("/test-trigger")
async def test_trigger_notification(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Student).where(Student.connection_status == "connected")
    )
    student = result.scalars().first()
    if not student:
        return {"error": "No connected students found"}

    now = datetime.now(timezone.utc)

    await manager.send_to_agent(student.unique_code, "warning", {
        "level": 1,
        "message": "TEST: You appear to be off-task. Please return to your studies.",
        "reason": "Watching YouTube (test)",
    })

    await manager.broadcast_faculty("faculty_notification", {
        "type": "off-task",
        "student_id": student.id,
        "student_name": student.name,
        "section": student.section,
        "activity": "Watching YouTube Shorts",
        "reason": "Entertainment video detected.",
        "explanation": "Testing off-task warnings and dashboard alerts.",
        "confidence": 94,
        "screenshot": None,
        "time": now.strftime("%I:%M %p"),
        "warning_count": 1,
    })

    await manager.broadcast_faculty("student_status", {
        "student_id": student.id,
        "name": student.name,
        "section": student.section,
        "status": "off-task",
        "activity": "Watching YouTube Shorts",
        "reason": "Entertainment video detected.",
        "explanation": "Testing off-task warnings.",
        "warning_count": 1,
        "screenshot": None,
        "last_seen": now.isoformat(),
    })

    return {
        "ok": True,
        "message": f"Test notification sent for {student.name} ({student.section})",
        "faculty_ws_connections": len(manager.faculty_connections),
        "agent_ws_connections": len(manager.agent_connections),
        "agent_ids": list(manager.agent_connections.keys()),
    }
