from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_session_factory(url: str) -> sessionmaker[Session]:
    # pool_pre_ping replaces connections the database dropped (e.g. after a restart).
    return sessionmaker(bind=create_engine(url, pool_pre_ping=True))


def get_db(request: Request) -> Iterator[Session]:
    """One database session per request, closed when the request ends."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
