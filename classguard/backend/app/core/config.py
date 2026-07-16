import os
from datetime import datetime, timezone
from typing import Optional


class Settings:
    def __init__(self):
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "kandukurisrikar10@gmail.com")
        self.ALGORITHM: str = "HS256"
        self.JWT_EXPIRE_MINUTES: int = 60 * 24
        self.ALLOWED_ORIGINS: list[str] = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://classguard.onrender.com",
            "https://classguard-backend.onrender.com",
            "https://classguard.vercel.app",
        ]
        self.BACKEND_URL: str = os.getenv("BACKEND_URL", "https://classguard-backend.onrender.com")
        self.AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "https://classguard-ai.onrender.com")
        self.WARNING_THRESHOLD: int = int(os.getenv("WARNING_THRESHOLD", "3"))
        
        # Load DATABASE_URL and translate postgres to postgresql+asyncpg for SQLAlchemy async compatibility
        raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./classguard.db")
        if raw_db_url.startswith("postgres://"):
            raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw_db_url.startswith("postgresql://"):
            raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.DATABASE_URL: str = raw_db_url
        
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.FACULTY_DEFAULT_EMAIL: str = os.getenv("FACULTY_DEFAULT_EMAIL", "kandukurisrikar10@gmail.com")
        self.FACULTY_DEFAULT_PASSWORD: str = os.getenv("FACULTY_DEFAULT_PASSWORD", "K.Srikar@10")
        self.GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")


settings = Settings()
