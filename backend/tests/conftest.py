import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app


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


@pytest.fixture(scope="session")
def engine(settings):
    engine = create_engine(settings.DATABASE_URL)
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
