import os
import uuid
from email.message import EmailMessage
from pathlib import Path

import boto3
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, start_session
from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Claim, Role, User
from app.photos.content_types import EXTENSIONS
from app.storage import PhotoStorage, get_storage


@pytest.fixture(autouse=True)
def outbox(monkeypatch) -> list[EmailMessage]:
    """Every test: emails land in this list instead of going to a mail server.

    Autouse, so no test that submits a claim sends real mail. A test can still swap in its
    own send_email with monkeypatch.setattr.
    """
    sent: list[EmailMessage] = []
    monkeypatch.setattr(
        "app.notifications.send_email", lambda message, settings: sent.append(message)
    )
    return sent


@pytest.fixture(scope="session")
def settings() -> Settings:
    # _env_file=None: tests never pick up a developer's backend/.env.
    return Settings(
        _env_file=None,
        DATABASE_URL=os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://warranty:warranty@localhost:5432/warranty_test",
        ),
        S3_ENDPOINT_URL=None,
        S3_BUCKET="test-bucket",
        S3_ACCESS_KEY_ID="testing",
        S3_SECRET_ACCESS_KEY="testing",
        APP_BASE_URL="http://app.test",
        SMTP_USERNAME=None,
    )


ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture(scope="session")
def engine(settings):
    """Once per test run: wipe the test database and rebuild it from the
    migrations, so the tests always run against the schema the migrations
    produce."""
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    cfg = Config(ALEMBIC_INI)
    # alembic.ini values use %-interpolation, so a literal % in the URL
    # (e.g. an encoded password) must be written as %%.
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    """A session inside one transaction that is rolled back after the test.

    Code under test may commit: with create_savepoint, its commits only
    release savepoints, and the outer rollback still undoes everything.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


class _UnclosableSession:
    """Wraps the test session for code that opens its own session (background
    tasks), so that closing it doesn't end the test's session."""

    def __init__(self, session: Session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def close(self):
        pass


@pytest.fixture
def app(settings, db):
    app = create_app(settings)

    def override_get_db():
        # In production, get_db's close() throws away whatever a request didn't commit.
        # Here every request shares the test's session, so each request gets its own
        # savepoint instead, rolled back at the end unless the route committed. Without
        # this, a route that forgot db.commit() would still pass its tests.
        request_work = db.begin_nested()
        try:
            yield db
        finally:
            if request_work.is_active:  # the route didn't commit
                request_work.rollback()

    app.dependency_overrides[get_db] = override_get_db
    app.state.session_factory = lambda: _UnclosableSession(db)
    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_user(db):
    """Call it to add a user: make_user(role=Role.reviewer, name="Kim")."""

    def _make_user(role: Role = Role.tech, name: str = "Tess Tech", email: str | None = None):
        user = User(name=name, role=role, email=email)
        db.add(user)
        db.flush()
        return user

    return _make_user


@pytest.fixture
def client_for(app, db, settings):
    """Call it with a user to get a TestClient already signed in as them."""

    def _client_for(user: User) -> TestClient:
        client = TestClient(app)
        client.cookies.set(COOKIE_NAME, start_session(db, user, settings))
        return client

    return _client_for


@pytest.fixture
def tech(make_user) -> User:
    return make_user()


@pytest.fixture
def reviewer(make_user) -> User:
    return make_user(role=Role.reviewer, name="Kim Reviewer", email="kim@example.com")


@pytest.fixture
def tech_client(client_for, tech) -> TestClient:
    return client_for(tech)


@pytest.fixture
def reviewer_client(client_for, reviewer) -> TestClient:
    return client_for(reviewer)


@pytest.fixture
def storage(app):
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        photo_storage = PhotoStorage(client=client, bucket="test-bucket")
        app.dependency_overrides[get_storage] = lambda: photo_storage
        yield photo_storage


@pytest.fixture
def put_upload(storage):
    """Call it to put a fake photo in storage as if the user's phone uploaded it:
    put_upload(tech) -> "uploads/{tech.id}/{random}.jpg"."""

    def _put_upload(
        user: User, content_type: str = "image/jpeg", body: bytes = b"fake-jpeg-bytes"
    ) -> str:
        key = f"uploads/{user.id}/{uuid.uuid4().hex}.{EXTENSIONS[content_type]}"
        storage.client.put_object(
            Bucket=storage.bucket, Key=key, Body=body, ContentType=content_type
        )
        return key

    return _put_upload


@pytest.fixture
def claim_payload(put_upload):
    """Call it to get a valid POST /api/claims body for that user, with fresh uploads:
    a VIN photo, then one damage photo described "Wheel RF"."""

    def _claim_payload(user: User) -> dict:
        return {
            "warranty_company": "Assurant",
            "customer_first_name": "Jane",
            "customer_last_name": "Smith",
            "vin": "1M8GDM9AXKP042788",
            "claim_number": None,
            "submission_tz": "America/New_York",
            "form_data": {
                "customer_phone": "(608) 555-0134",
                "customer_address": "100 Main St",
                "customer_city": "Cary",
                "customer_state": "NC",
                "customer_zip": "27519",
                "vehicle_year": 2024,
                "vehicle_make": "Honda",
                "vehicle_model": "Civic",
            },
            "photos": [
                {"key": put_upload(user), "kind": "vin"},
                {"key": put_upload(user), "kind": "damage", "description": "Wheel RF"},
            ],
        }

    return _claim_payload


@pytest.fixture
def make_claim(client_for, claim_payload, db):
    """Call it to submit a claim through the API as that tech:
    make_claim(tech, claim_number="AUTH-51") -> Claim."""

    def _make_claim(owner: User, **overrides) -> Claim:
        response = client_for(owner).post("/api/claims", json=claim_payload(owner) | overrides)
        assert response.status_code == 201, response.text
        return db.get(Claim, response.json()["id"])

    return _make_claim
