import secrets
import string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.device import Device
from app.schemas.student import StudentCreate, StudentResponse, LinkDeviceRequest, LinkDeviceResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/api/students", tags=["students"])


def generate_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "CG-" + "".join(secrets.choice(chars) for _ in range(6))


@router.post("/", response_model=StudentResponse)
async def create_student(
    body: StudentCreate,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    unique_code = generate_code()

    existing = await db.execute(select(Student).where(Student.unique_code == unique_code))
    while existing.scalar_one_or_none():
        unique_code = generate_code()
        existing = await db.execute(select(Student).where(Student.unique_code == unique_code))

    student = Student(
        name=body.name,
        section=body.section,
        unique_code=unique_code,
        connection_status="not_connected",
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.get("/", response_model=list[StudentResponse])
async def list_students(
    section: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    query = select(Student)
    if section:
        query = query.where(Student.section == section)
    query = query.order_by(Student.section, Student.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/sections")
async def list_sections(
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    result = await db.execute(select(Student.section).distinct().order_by(Student.section))
    return {"sections": [r[0] for r in result.all()]}


@router.delete("/{student_id}")
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await db.delete(student)
    await db.commit()
    return {"message": "Student deleted"}


@router.post("/{student_id}/re-enable")
async def re_enable_monitoring(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student.monitoring_paused = False
    student.pause_reason = None
    student.monitoring_enabled = True
    await db.commit()

    from app.ws.manager import manager
    await manager.send_to_agent(student.unique_code, "monitoring_started", {"interval_seconds": 1})

    return {"message": "Monitoring re-enabled"}


@router.post("/link-device", response_model=LinkDeviceResponse)
async def link_device(body: LinkDeviceRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Student).where(Student.unique_code == body.code))
    student = result.scalar_one_or_none()

    if not student:
        return LinkDeviceResponse(
            success=False,
            message="Invalid code. Please contact your faculty.",
        )

    if student.connection_status == "connected":
        device_result = await db.execute(
            select(Device).where(
                Device.student_id == student.id,
                Device.status == "active",
            )
        )
        existing_device = device_result.scalar_one_or_none()
        if existing_device:
            return LinkDeviceResponse(
                success=True,
                message="Device already linked. Reconnecting.",
                device_token=existing_device.device_token,
                student_name=student.name,
                section=student.section,
            )

    device_token = secrets.token_hex(32)

    student.connection_status = "connected"
    student.last_seen = datetime.now(timezone.utc)

    device = Device(
        student_id=student.id,
        device_token=device_token,
        connected_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        status="active",
    )
    db.add(device)
    await db.commit()

    return LinkDeviceResponse(
        success=True,
        message="Device linked successfully!",
        device_token=device_token,
        student_name=student.name,
        section=student.section,
    )


@router.post("/register-device")
async def register_device(body: dict, db: AsyncSession = Depends(get_db)):
    """
    Simplified endpoint for agent registration. Takes student_code and returns device_token.
    This endpoint is used by the student desktop agent.
    """
    student_code = body.get("student_code")

    if not student_code:
        raise HTTPException(status_code=400, detail="student_code required")

    result = await db.execute(select(Student).where(Student.unique_code == student_code))
    student = result.scalar_one_or_none()

    if not student:
        return {"error": "Invalid code. Please contact your faculty."}

    if student.connection_status == "connected":
        device_result = await db.execute(
            select(Device).where(
                Device.student_id == student.id,
                Device.status == "active",
            )
        )
        existing_device = device_result.scalar_one_or_none()
        if existing_device:
            return {
                "device_token": existing_device.device_token,
                "student_name": student.name,
                "section": student.section,
            }

    device_token = secrets.token_hex(32)

    student.connection_status = "connected"
    student.last_seen = datetime.now(timezone.utc)

    device = Device(
        student_id=student.id,
        device_token=device_token,
        connected_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        status="active",
    )
    db.add(device)
    await db.commit()

    return {
        "device_token": device_token,
        "student_name": student.name,
        "section": student.section,
    }


@router.get("/{student_id}/history")
async def get_student_history(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    from app.models.monitoring_log import MonitoringLog
    result = await db.execute(
        select(MonitoringLog)
        .where(MonitoringLog.student_id == student_id)
        .order_by(MonitoringLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "status": log.status,
            "confidence": log.confidence,
            "reason": log.reason,
            "window_title": log.window_title,
            "screenshot": log.screenshot_path,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
