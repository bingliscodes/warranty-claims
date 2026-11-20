from typing import Literal

from fastapi import Request
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

DEV_S3_ACCESS_KEY = "dev-access-key"
DEV_S3_SECRET_KEY = "dev-secret-key"
DEV_DATABASE_PASSWORD = "warranty"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: Literal["development", "production"] = "development"

    DATABASE_URL: str = "postgresql+psycopg://warranty:warranty@localhost:5432/warranty"

    SESSION_COOKIE_SECURE: bool = False
    SESSION_TTL_DAYS: int = 365

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]
    APP_BASE_URL: str = "http://localhost:5173"

    S3_ENDPOINT_URL: str | None = "http://localhost:9000"
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = "warranty-photos"
    S3_ACCESS_KEY_ID: str = DEV_S3_ACCESS_KEY
    S3_SECRET_ACCESS_KEY: str = DEV_S3_SECRET_KEY
    MAX_UPLOAD_BYTES: int = 30_000_000

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_STARTTLS: bool = False
    MAIL_FROM: str = "warranty-app@localhost"

    VPIC_BASE_URL: str = "https://vpic.nhtsa.dot.gov/api"

    @model_validator(mode="after")
    def _refuse_unsafe_production_settings(self) -> Settings:
        if self.APP_ENV != "production":
            return self

        problems = []
        if not self.SESSION_COOKIE_SECURE:
            problems.append("SESSION_COOKIE_SECURE must be true")
        if not self.APP_BASE_URL.startswith("https://"):
            problems.append("APP_BASE_URL must start with https://")
        if not all(origin.startswith("https://") for origin in self.ALLOWED_ORIGINS):
            problems.append("ALLOWED_ORIGINS entries must all start with https://")
        if self.S3_ACCESS_KEY_ID == DEV_S3_ACCESS_KEY:
            problems.append("S3_ACCESS_KEY_ID is still the development value")
        if self.S3_SECRET_ACCESS_KEY == DEV_S3_SECRET_KEY:
            problems.append("S3_SECRET_ACCESS_KEY is still the development value")
        if make_url(self.DATABASE_URL).password == DEV_DATABASE_PASSWORD:
            problems.append("DATABASE_URL still uses the development password")

        if problems:
            raise ValueError("Unsafe settings for APP_ENV=production: " + "; ".join(problems))
        return self


def get_settings(request: Request) -> Settings:
    """FastAPI dependency: the Settings that create_app() was given."""
    return request.app.state.settings
