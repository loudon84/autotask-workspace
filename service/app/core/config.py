"""Application settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "nodeskclaw-task"
    APP_VERSION: str = "dev"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 4520
    PUBLIC_BASE_URL: str = "http://127.0.0.1:4520"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nodeskclaw_task"
    DB_POOL_SIZE: int = 10
    DB_POOL_MAX_OVERFLOW: int = 20

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    NODESKCLAW_BACKEND_URL: str = "http://127.0.0.1:4510"
    NODESKCLAW_AUTH_ME_PATH: str = "/api/v1/auth/me"
    USER_CACHE_TTL_MINUTES: int = 10

    ARTIFACT_STORAGE: str = "local"
    ARTIFACT_LOCAL_DIR: str = "./storage/artifacts"
    ARTIFACT_UPLOAD_BASE_URL: str = ""
    ARTIFACT_DOWNLOAD_BASE_URL: str = ""
    S3_ENDPOINT: str = ""
    S3_REGION: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_KEY_PREFIX: str = "autotask"
    S3_PRESIGN_EXPIRES_SECONDS: int = 3600

    RPA_ENGINE_BASE_URL: str = ""
    RPA_ENGINE_VALIDATE_BINDING: bool = True

    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000"]

    WORKER_LEASE_TTL_SECONDS: int = 60
    WORKER_HEARTBEAT_TIMEOUT_SECONDS: int = 60

    SUCCESSOR_JOB_ENABLED: bool = False
    SUCCESSOR_JOB_POLL_INTERVAL_SECONDS: float = Field(default=2.0, gt=0, le=300)
    SUCCESSOR_JOB_BATCH_SIZE: int = Field(default=10, ge=1, le=100)
    SUCCESSOR_JOB_MAX_ATTEMPTS: int = Field(default=10, ge=1, le=100)

    SCAN_JOB_ENABLED: bool = False
    SCAN_JOB_HOUR: int = Field(default=8, ge=0, le=23)
    SCAN_JOB_MINUTE: int = Field(default=0, ge=0, le=59)
    SCAN_JOB_POLL_INTERVAL_SECONDS: float = Field(default=60.0, gt=0, le=3600)

    SIGN_POLL_JOB_ENABLED: bool = False
    SIGN_POLL_INTERVAL_SECONDS: float = Field(default=1800.0, gt=0, le=86400)

    SEED_DATA_ENABLED: bool = True
    SKIP_AUTO_MIGRATE: bool = False
    SEED_DATA_DIR: str = "app/data/seed"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
