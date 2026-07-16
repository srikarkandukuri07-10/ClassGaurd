from datetime import datetime, timezone
from typing import Optional


class Settings:
    def __init__(self):
        self.SECRET_KEY: str = "kandukurisrikar10@gmail.com"  # For demo, email as key
        self.ALGORITHM: str = "HS256"
        self.JWT_EXPIRE_MINUTES: int = 60 * 24
        self.ALLOWED_ORIGINS: list[str] = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://classguard.onrender.com",
            "https://classguard-backend.onrender.com",
        ]
        self.BACKEND_URL: str = "https://classguard-backend.onrender.com"
        self.AI_SERVICE_URL: str = "https://classguard-ai.onrender.com" if "classguard-ai.onrender.com" in ["https://classguard-ai.onrender.com", "http://localhost:8002"] else "http://localhost:8002"
        self.WARNING_THRESHOLD: int = 3
        self.DATABASE_URL: str = "sqlite+aiosqlite:///./classguard.db"
        self.REDIS_URL: str = "redis://localhost:6379/0"
        self.FACULTY_DEFAULT_EMAIL: str = "kandukurisrikar10@gmail.com"
        self.FACULTY_DEFAULT_PASSWORD: str = "K.Srikar@10"
        self.GEMINI_API_KEY: Optional[str] = None


settings = Settings()
