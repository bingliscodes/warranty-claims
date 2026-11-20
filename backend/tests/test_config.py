import pytest
from pydantic import ValidationError

from app.config import Settings

SAFE = dict(
    APP_ENV="production",
    SESSION_COOKIE_SECURE=True,
    APP_BASE_URL="https://claims.example.com",
    ALLOWED_ORIGINS=["https://claims.example.com"],
    DATABASE_URL="postgresql+psycopg://warranty:s3cret-db@db.example.com:5432/warranty",
    S3_ACCESS_KEY_ID="AKEXAMPLE",
    S3_SECRET_ACCESS_KEY="example-secret",
)


def test_production_accepts_safe_settings():
    assert Settings(_env_file=None, **SAFE).APP_ENV == "production"


def test_production_rejects_dev_defaults_and_names_each_problem():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, APP_ENV="production")
    message = str(exc.value)
    for name in [
        "SESSION_COOKIE_SECURE",
        "APP_BASE_URL",
        "ALLOWED_ORIGINS",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "DATABASE_URL",
    ]:
        assert name in message


@pytest.mark.parametrize(
    "override",
    [
        {"SESSION_COOKIE_SECURE": False},
        {"ALLOWED_ORIGINS": ["https://claims.example.com", "http://192.168.1.50:5173"]},
        {"S3_SECRET_ACCESS_KEY": "dev-secret-key"},
        {"DATABASE_URL": "postgresql+psycopg://warranty:warranty@db.example.com:5432/warranty"},
    ],
)
def test_production_rejects_each_unsafe_setting(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**SAFE, **override})
