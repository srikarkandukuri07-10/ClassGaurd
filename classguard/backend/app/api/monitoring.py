from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.device import Device
from app.models.monitoring_session import MonitoringSession
from app.schemas.monitoring import MonitoringStateResponse
from app.ws.manager import manager

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.post("/start")
async def start_monitoring(
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    students = await db.execute(select(Student))
    for s in students.scalars().all():
        s.monitoring_enabled = True
        s.monitoring_paused = False
        if s.connection_status == "connected":
            if s.current_status == "offline":
                s.current_status = "monitoring"
        session = MonitoringSession(student_id=s.id, is_active=True)
        db.add(session)
    await db.commit()

    await manager.broadcast_agents("monitoring_started", {"interval_seconds": 1})
    return {"message": "Monitoring started"}


@router.post("/stop")
async def stop_monitoring(
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    students = await db.execute(select(Student))
    for s in students.scalars().all():
        s.monitoring_enabled = False
        if s.connection_status == "connected":
            s.current_status = "offline"

    sessions = await db.execute(
        select(MonitoringSession).where(MonitoringSession.is_active == True)
    )
    for sess in sessions.scalars().all():
        sess.is_active = False
        sess.ended_at = now

    await db.commit()

    await manager.broadcast_agents("monitoring_stopped", {})
    return {"message": "Monitoring stopped"}


@router.get("/state", response_model=MonitoringStateResponse)
async def get_monitoring_state(
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    students = await db.execute(select(Student))
    all_students = students.scalars().all()

    sections = set()
    studying = off_task = suspicious = offline = 0
    for s in all_students:
        sections.add(s.section)
        if s.current_status == "studying":
            studying += 1
        elif s.current_status == "off-task":
            off_task += 1
        elif s.current_status == "suspicious":
            suspicious += 1
        elif s.current_status in ("offline", "disconnected"):
            offline += 1

    return MonitoringStateResponse(
        monitoring_active=any(s.monitoring_enabled for s in all_students),
        active_sections=sorted(sections),
        total_students=len(all_students),
        studying_count=studying,
        off_task_count=off_task,
        suspicious_count=suspicious,
        offline_count=offline,
    )


@router.post("/heartbeat")
async def heartbeat(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    device_token = body.get("device_token")
    if not device_token:
        raise HTTPException(status_code=400, detail="device_token required")

    result = await db.execute(
        select(Device).where(
            Device.device_token == device_token,
            Device.status == "active",
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    now = datetime.now(timezone.utc)
    device.last_seen = now

    student_result = await db.execute(select(Student).where(Student.id == device.student_id))
    student = student_result.scalar_one()
    student.last_seen = now
    student.connection_status = "connected"

    await db.commit()

    return {"ok": True}


@router.post("/reconnect")
async def reconnect(body: dict, db: AsyncSession = Depends(get_db)):
    device_token = body.get("device_token")
    if not device_token:
        raise HTTPException(status_code=400, detail="device_token required")

    result = await db.execute(
        select(Device).where(
            Device.device_token == device_token,
            Device.status == "active",
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found. Please re-link.")

    student_result = await db.execute(select(Student).where(Student.id == device.student_id))
    student = student_result.scalar_one()

    now = datetime.now(timezone.utc)
    device.last_seen = now
    student.last_seen = now
    student.connection_status = "connected"

    await db.commit()

    # Broadcast updated student status to faculty dashboard instantly
    await manager.broadcast_faculty("student_status", {
        "student_id": student.id,
        "name": student.name,
        "section": student.section,
        "status": student.current_status,
        "reason": student.reason or "",
        "warning_count": student.warning_count,
        "screenshot": student.latest_screenshot,
        "last_seen": now.isoformat(),
    })

    return {
        "ok": True,
        "student_name": student.name,
        "section": student.section,
        "device_token": device_token,
        "monitoring_enabled": student.monitoring_enabled,
        "monitoring_paused": student.monitoring_paused,
    }
