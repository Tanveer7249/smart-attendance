import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "PI Pascals Attendance System"
    COMPANY_NAME: str = "PI Pascals Institute PVT LTD"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-in-production-smart-attendance-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    
    # SQLite default for instant zero-dependency local runs; works out-of-the-box or PostgreSQL via env
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./smart_attendance.db")
    
    # Policy defaults
    MIN_ATTENDANCE_PERCENTAGE: float = 75.0
    DEFAULT_LATE_THRESHOLD_MINUTES: int = 15
    QR_TOKEN_EXPIRY_SECONDS: int = 30
    DEFAULT_GPS_RADIUS_METERS: float = 150.0

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

