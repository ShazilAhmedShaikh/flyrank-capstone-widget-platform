"""
Configuration module for the Embeddable Widget Platform.
Loads environment variables with safe defaults and validates settings.
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "FlyRank Embeddable Widget Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    BASE_URL: str = "http://localhost:8000"

    # Security & JWT Auth
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-only-for-local-testing"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./widget_platform.db"

    # Boundaries & Sizing
    MAX_PAYLOAD_SIZE_BYTES: int = 65536  # 64 KB boundary limit

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE_IP: int = 30
    RATE_LIMIT_PER_MINUTE_WIDGET: int = 60
    RATE_LIMIT_BURST_MAX: int = 5
    RATE_LIMIT_BURST_WINDOW_SECONDS: int = 10

    # Geolocation Providers (Fallback Chain)
    GEO_PROVIDER_A_URL: str = "http://ip-api.com/json/{ip}"
    GEO_PROVIDER_B_URL: str = "https://ipapi.co/{ip}/json/"
    GEO_TIMEOUT_SECONDS: float = 2.5

    # Simulation / Mock Toggles for Automated Probes
    SIMULATE_GEO_PROVIDER_A_DOWN: bool = False
    SIMULATE_GEO_PROVIDER_B_DOWN: bool = False
    SIMULATE_SIDE_EFFECT_FAILURE: bool = False

    # Secondary Side Effect Settings
    NOTIFICATION_CHANNEL: str = "log"
    ALERT_WEBHOOK_URL: str = "http://localhost:9999/webhook-mock"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@widgets.flyrank.local"

    # CORS Allowed Origins
    CORS_ALLOW_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
