from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import engine, Base, async_session
from app.api import auth, students, monitoring, disable_requests, ai_events
from app.ws.routes import router as ws_router
from app.models.student import Student


async def check_heartbeats():
    while True:
        await asyncio.sleep(15)
        try:
            async with async_session() as db:
                now = datetime.now(timezone.utc)
                result = await db.execute(select(Student))
                for student in result.scalars().all():
                    if student.connection_status == "connected" and student.last_seen:
                        diff = (now - student.last_seen).total_seconds()
                        if diff > 30 and student.current_status not in ("offline", "disconnected"):
                            student.connection_status = "disconnected"
                            student.current_status = "disconnected"
                            if student.monitoring_enabled and not student.monitoring_paused:
                                student.monitoring_enabled = False
                            from app.ws.manager import manager
                            await manager.broadcast_faculty("faculty_notification", {
                                "type": "offline",
                                "student_name": student.name,
                                "section": student.section,
                                "reason": "Monitoring offline",
                            })
                await db.commit()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Safely check and add columns using reflection to avoid transaction corruption
    try:
        async with engine.connect() as conn:
            def get_columns(connection):
                from sqlalchemy import inspect
                inspector = inspect(connection)
                return [c["name"] for c in inspector.get_columns("monitoring_logs")]
            
            existing_columns = await conn.run_sync(get_columns)
            
            for col_name, col_type in [("activity", "VARCHAR(500)"), ("explanation", "VARCHAR(1000)")]:
                if col_name not in existing_columns:
                    async with engine.begin() as alter_conn:
                        await alter_conn.execute(f"ALTER TABLE monitoring_logs ADD COLUMN {col_name} {col_type}")
                    print(f"[Migration] Added column {col_name} to monitoring_logs.")
    except Exception as e:
        print(f"[Migration Error] Failed to run migrations: {e}")
    
    # Auto-seed the single admin faculty account if it doesn't exist
    from app.core.security import hash_password
    from app.models.faculty import Faculty
    async with async_session() as db:
        result = await db.execute(select(Faculty).where(Faculty.email == "kandukurisrikar10@gmail.com"))
        user = result.scalar_one_or_none()
        if not user:
            admin_user = Faculty(
                name="Srikar Kandukuri",
                email="kandukurisrikar10@gmail.com",
                hashed_password=hash_password("K.Srikar@10"),
            )
            db.add(admin_user)
            await db.commit()

    task = asyncio.create_task(check_heartbeats())
    yield
    task.cancel()
    await engine.dispose()


from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="ClassGuard API", lifespan=lifespan)

# Ensure static directories exist
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "screenshots"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://classguard.onrender.com",
        "https://classguard-backend.onrender.com",
        "https://classguard-ai.onrender.com",
        "https://classguard.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(monitoring.router)
app.include_router(disable_requests.router)
app.include_router(ai_events.router)
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/debug-data")
async def debug_data():
    from app.models.student import Student
    from app.models.device import Device
    from app.models.warning import Warning as WarningModel
    from app.models.monitoring_log import MonitoringLog
    try:
        async with async_session() as db:
            s_res = await db.execute(select(Student))
            students = s_res.scalars().all()
            
            d_res = await db.execute(select(Device))
            devices = d_res.scalars().all()
            
            w_res = await db.execute(select(WarningModel))
            warnings = w_res.scalars().all()
            
            l_res = await db.execute(select(MonitoringLog).order_by(MonitoringLog.created_at.desc()).limit(10))
            logs = l_res.scalars().all()
            
            return {
                "students": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "unique_code": s.unique_code,
                        "monitoring_enabled": s.monitoring_enabled,
                        "monitoring_paused": s.monitoring_paused,
                        "current_status": s.current_status,
                        "warning_count": s.warning_count,
                    }
                    for s in students
                ],
                "devices": [
                    {
                        "id": d.id,
                        "student_id": d.student_id,
                        "device_token": d.device_token,
                        "status": d.status,
                        "last_seen": str(d.last_seen),
                    }
                    for d in devices
                ],
                "warnings": [
                    {
                        "id": w.id,
                        "student_id": w.student_id,
                        "level": w.level,
                        "message": w.message,
                        "created_at": str(w.created_at),
                    }
                    for w in warnings
                ],
                "logs": [
                    {
                        "id": l.id,
                        "student_id": l.student_id,
                        "status": l.status,
                        "activity": l.activity,
                        "reason": l.reason,
                        "window_title": l.window_title,
                        "created_at": str(l.created_at),
                    }
                    for l in logs
                ]
            }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
