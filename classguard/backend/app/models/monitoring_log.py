from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class MonitoringLog(Base):
    __tablename__ = "monitoring_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    status = Column(String(50), nullable=False)  # studying / suspicious / off-task
    confidence = Column(Float, default=1.0)
    reason = Column(String(500), nullable=True)
    window_title = Column(String(500), nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="monitoring_logs")
