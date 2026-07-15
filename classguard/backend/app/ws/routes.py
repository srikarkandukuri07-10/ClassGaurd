from fastapi import APIRouter, WebSocket, Depends
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import async_session
from app.core.classifier import ScreenClassifier
from app.models.device import Device
from app.models.student import Student
from app.models.warning import Warning as WarningModel
from app.models.monitoring_log import MonitoringLog
from app.ws.manager import manager
from datetime import datetime, timezone
import asyncio
import time
import os
import base64
import uuid

router = APIRouter()
classifier = ScreenClassifier()


async def classify_and_notify(device: Device, student: Student, window_title: str, screenshot: str):
    """Run AI classification and fire warnings/notifications — all inside the same process."""
    try:
        result = await classifier.classify(image_b64=screenshot, window_title=window_title)
        status = result.get("status", "studying")
        reason = result.get("reason", "")
        confidence = result.get("confidence", 0.8)

        async with async_session() as db:
            # Re-fetch fresh student to avoid stale state
            s_result = await db.execute(select(Student).where(Student.id == student.id))
            s = s_result.scalar_one_or_none()
            if not s:
                return

            if not s.monitoring_enabled or s.monitoring_paused:
                return

            now = datetime.now(timezone.utc)
            s.last_seen = now
            s.current_status = status

            # Save screenshot
            screenshot_url = None
            if screenshot:
                try:
                    static_dir = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "..", "static")
                    )
                    os.makedirs(os.path.join(static_dir, "screenshots"), exist_ok=True)
                    img_b64 = screenshot.split(",")[1] if "," in screenshot else screenshot
                    image_data = base64.b64decode(img_b64)
                    filename = f"{uuid.uuid4()}.jpg"
                    filepath = os.path.join(static_dir, "screenshots", filename)
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                    screenshot_url = f"/static/screenshots/{filename}"
                    s.latest_screenshot = screenshot_url
                except Exception as e:
                    print("Screenshot save error:", e)

            # Save monitoring log
            log = MonitoringLog(
                student_id=s.id,
                status=status,
                confidence=confidence,
                reason=reason or window_title or "Monitoring",
                window_title=window_title or "",
                screenshot_path=screenshot_url,
            )
            db.add(log)

            if status == "off-task":
                s.warning_count += 1

                warning = WarningModel(
                    student_id=s.id,
                    level=s.warning_count,
                    reason=reason or window_title or "",
                )
                db.add(warning)

                warning_messages = {
                    1: "⚠️ First Warning: You appear to be off-task. Please return to your studies.",
                    2: "⚠️ Second Warning: Please return to class activities immediately.",
                    3: "🚨 Final Warning: Faculty has been notified. Please stop immediately.",
                }
                msg = warning_messages.get(
                    s.warning_count,
                    f"🚨 Warning #{s.warning_count}: Faculty has been notified.",
                )

                # Notify student via WebSocket
                await manager.send_to_agent(s.unique_code, "warning", {
                    "level": min(s.warning_count, 3),
                    "message": msg,
                    "reason": reason,
                })

                # Notify faculty
                await manager.broadcast_faculty("faculty_notification", {
                    "type": "off-task",
                    "student_id": s.id,
                    "student_name": s.name,
                    "section": s.section,
                    "reason": reason or "Off-task activity",
                    "confidence": int(confidence * 100),
                    "screenshot": screenshot_url,
                    "time": now.strftime("%I:%M %p"),
                    "warning_count": s.warning_count,
                })

            elif status == "suspicious":
                await manager.broadcast_faculty("faculty_notification", {
                    "type": "suspicious",
                    "student_id": s.id,
                    "student_name": s.name,
                    "section": s.section,
                    "reason": reason or "Suspicious activity",
                    "confidence": int(confidence * 100),
                    "screenshot": screenshot_url,
                    "time": now.strftime("%I:%M %p"),
                    "warning_count": s.warning_count,
                })

            # Always push status update to faculty dashboard
            await manager.broadcast_faculty("student_status", {
                "student_id": s.id,
                "name": s.name,
                "section": s.section,
                "status": status,
                "reason": reason or window_title or "",
                "warning_count": s.warning_count,
                "screenshot": screenshot_url,
                "last_seen": now.isoformat(),
            })

            await db.commit()

    except Exception as e:
        print(f"[AI classify_and_notify error]: {e}")


@router.websocket("/ws/faculty")
async def faculty_websocket(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if not email:
            await ws.close(code=4001)
            return
    except JWTError:
        await ws.close(code=4001)
        return

    faculty_id = hash(email)
    await manager.connect_faculty(faculty_id, ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        manager.disconnect_faculty(faculty_id)


@router.websocket("/ws/agent")
async def agent_websocket(ws: WebSocket):
    device_token = ws.query_params.get("device_token")
    if not device_token:
        await ws.close(code=4001)
        return

    async with async_session() as db:
        result = await db.execute(
            select(Device).where(
                Device.device_token == device_token,
                Device.status == "active",
            )
        )
        device = result.scalar_one_or_none()
        if not device:
            await ws.close(code=4001)
            return

        student_result = await db.execute(
            select(Student).where(Student.id == device.student_id)
        )
        student = student_result.scalar_one()
        student.connection_status = "connected"
        student.last_seen = datetime.now(timezone.utc)
        device.last_seen = datetime.now(timezone.utc)
        await db.commit()

        device_id = student.unique_code

    await manager.connect_agent(device_id, ws)
    try:
        # Sync monitoring state to the agent on first connect
        if student.monitoring_paused:
            await manager.send_to_agent(device_id, "monitoring_paused", {"reason": getattr(student, 'pause_reason', '')})
        elif student.monitoring_enabled:
            await manager.send_to_agent(device_id, "monitoring_started", {})
        else:
            await manager.send_to_agent(device_id, "monitoring_stopped", {})

        last_ai_check = 0

        while True:
            data = await ws.receive_json()
            event = data.get("event", "")

            if event == "screen_frame":
                screenshot = data.get("screenshot", "")
                window_title = data.get("window_title", "")

                # Broadcast live frame to faculty dashboard
                await manager.broadcast_faculty("live_frame", {
                    "student_id": device.student_id,
                    "screenshot": screenshot,
                    "window_title": window_title,
                })

                # Run AI classification every 5 seconds
                current_time = time.time()
                if current_time - last_ai_check >= 5:
                    last_ai_check = current_time
                    asyncio.create_task(
                        classify_and_notify(device, student, window_title, screenshot)
                    )

            elif event == "status_update":
                status = data.get("status", "")
                reason = data.get("reason", "")
                async with async_session() as db:
                    s_result = await db.execute(
                        select(Student).where(Student.id == device.student_id)
                    )
                    s = s_result.scalar_one()
                    s.last_seen = datetime.now(timezone.utc)
                    await db.commit()

                await manager.broadcast_faculty("student_status", {
                    "student_id": device.student_id,
                    "status": status,
                    "reason": reason,
                })

    except Exception as e:
        print(f"[Agent WS error]: {e}")
    finally:
        manager.disconnect_agent(device_id)
