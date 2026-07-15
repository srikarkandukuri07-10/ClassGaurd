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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
