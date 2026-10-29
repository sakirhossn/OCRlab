"""Application configuration settings for Unlimited OCR Cloud."""

from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = "Unlimited OCR Cloud"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])

    # Database
    database_url: str = "sqlite+aiosqlite:///./storage/ocrlab.db"
    db_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False  # Falls back to in-memory token bucket if False

    # Security & Cryptography
    secret_key: str = "insecure-dev-key-change-in-production-must-be-32-bytes"
    storage_encryption_key: str = "super-secret-storage-aes-256-key-32b"  # 32 bytes for AES-256
    worker_auth_token: str = "worker-secret-token-change-me"

    # Storage Paths
    storage_dir: Path = Path("./storage/vault")
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    max_pages_per_doc: int = 200

    # Quotas & Defaults
    default_monthly_quota_pages: int = 1000
    default_rate_limit_rpm: int = 60

    # Worker Leasing
    lease_timeout_seconds: int = 300  # 5 minutes
    lease_heartbeat_extension_seconds: int = 120
    max_job_retries: int = 3

    # Webhook
    webhook_retry_delays_seconds: List[int] = Field(
        default_factory=lambda: [30, 120, 600, 3600, 21600]
    )
    webhook_timeout_seconds: float = 15.0


settings = Settings()
