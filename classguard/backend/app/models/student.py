from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    section = Column(String(10), nullable=False, index=True)
    unique_code = Column(String(20), unique=True, nullable=False, index=True)

    connection_status = Column(String(50), default="not_connected")
    last_seen = Column(DateTime(timezone=True), nullable=True)

    monitoring_enabled = Column(Boolean, default=False)
    monitoring_paused = Column(Boolean, default=False)
    pause_reason = Column(String(500), nullable=True)

    current_status = Column(String(50), default="offline")
    warning_count = Column(Integer, default=0)
    latest_screenshot = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    devices = relationship("Device", back_populates="student", cascade="all, delete-orphan")
    disable_requests = relationship("DisableRequest", back_populates="student", cascade="all, delete-orphan")
    warnings = relationship("Warning", back_populates="student", cascade="all, delete-orphan")
    monitoring_sessions = relationship("MonitoringSession", back_populates="student", cascade="all, delete-orphan")
    monitoring_logs = relationship("MonitoringLog", back_populates="student", cascade="all, delete-orphan")
