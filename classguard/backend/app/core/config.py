from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///C:/Users/Admin/OneDrive/Desktop/backup-takeover/classguard/backend/classguard.db"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    AI_SERVICE_URL: str = "http://localhost:8001"

    WARNING_THRESHOLD: int = 3
    HEARTBEAT_TIMEOUT_SECONDS: int = 30
    GEMINI_API_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
