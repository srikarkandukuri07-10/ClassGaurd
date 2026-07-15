from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.faculty import Faculty
from app.models.student import Student
from app.models.device import Device
from app.models.disable_request import DisableRequest
from app.schemas.disable_request import DisableRequestCreate, DisableRequestResponse, DisableRequestAction
from app.ws.manager import manager

router = APIRouter(prefix="/api/disable-requests", tags=["disable-requests"])


@router.post("/", response_model=dict)
async def create_disable_request(
    body: DisableRequestCreate,
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
        raise HTTPException(status_code=404, detail="Student not found")

    student_result = await db.execute(
        select(Student).where(Student.id == device.student_id)
    )
    student = student_result.scalar_one()

    req = DisableRequest(student_id=student.id, reason=body.reason)
    db.add(req)
    await db.commit()

    await manager.broadcast_faculty("disable_requested", {
        "student_name": student.name,
        "section": student.section,
        "reason": body.reason,
        "request_id": req.id,
        "student_id": student.id,
    })

    return {"message": "Disable request submitted", "request_id": req.id}


@router.get("/", response_model=list[DisableRequestResponse])
async def list_disable_requests(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    query = select(DisableRequest, Student).join(
        Student, DisableRequest.student_id == Student.id
    )
    if status_filter:
        query = query.where(DisableRequest.status == status_filter)
    query = query.order_by(DisableRequest.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    return [
        DisableRequestResponse(
            id=req.id,
            student_id=req.student_id,
            student_name=student.name,
            section=student.section,
            reason=req.reason,
            status=req.status,
            created_at=req.created_at,
            reviewed_at=req.reviewed_at,
        )
        for req, student in rows
    ]


@router.post("/review")
async def review_disable_request(
    body: DisableRequestAction,
    db: AsyncSession = Depends(get_db),
    _: Faculty = Depends(get_current_user),
):
    result = await db.execute(
        select(DisableRequest).where(DisableRequest.id == body.request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    req.status = body.action
    req.reviewed_at = datetime.now(timezone.utc)

    if body.action == "approved":
        student_result = await db.execute(
            select(Student).where(Student.id == req.student_id)
        )
        student = student_result.scalar_one()
        student.monitoring_paused = True
        student.monitoring_enabled = False
        student.pause_reason = req.reason

        await manager.send_to_agent(student.unique_code, "monitoring_paused", {
            "reason": req.reason,
        })

    await db.commit()
    return {"message": f"Request {body.action}"}
