import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth import COOKIE_NAME, start_session
from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Role, User


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
        yield db

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
