import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SHADOWLINK FIELD"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SHADOWLINK_SECRET_KEY", "dev-secret-key-change-in-production-field-ops-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for field durability

    # Database: SQLite in WAL mode for local gateway, or PostgreSQL connection string
    DEFAULT_DB_PATH: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../shadowlink_field.db")
    )
    DATABASE_URL: str = os.getenv(
        "SHADOWLINK_DATABASE_URL",
        f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../shadowlink_field.db'))}",
    )

    # Messaging Engine Defaults
    DEFAULT_BASE_DELAY_SEC: float = 2.0
    DEFAULT_MAX_DELAY_SEC: float = 60.0
    DEFAULT_JITTER_SEC: float = 0.5
    DEFAULT_MAX_ATTEMPTS: int = 5
    DEFAULT_LEASE_TIMEOUT_SEC: float = 30.0
    MAX_PAYLOAD_BYTES: int = 65536  # 64 KB limit

    class Config:
        env_prefix = "SHADOWLINK_"
        case_sensitive = True


settings = Settings()
