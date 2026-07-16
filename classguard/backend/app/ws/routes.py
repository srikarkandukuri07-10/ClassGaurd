from fastapi import APIRouter, WebSocket, Depends
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import async_session
from app.models.device import Device
from app.models.student import Student
from app.ws.manager import manager
from datetime import datetime, timezone
import asyncio
import time

# Import process_student_frame directly to keep AI pipeline consistent
from app.api.ai_events import process_student_frame

router = APIRouter()


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
        # Sync monitoring state to the agent on first connect (default capture interval: 1s)
        if student.monitoring_paused:
            await manager.send_to_agent(device_id, "monitoring_paused", {"reason": getattr(student, 'pause_reason', '')})
        elif student.monitoring_enabled:
            await manager.send_to_agent(device_id, "monitoring_started", {"interval_seconds": 1})
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

                # Check frame asynchronously using background classifier
                asyncio.create_task(
                    process_student_frame(device_token, window_title, screenshot)
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
