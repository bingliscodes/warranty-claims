"""Who is making this request? Anonymous test-mode sessions (design §6).

The role picker creates a user and a session. The browser holds the session
token in an HttpOnly cookie; the database holds only its SHA-256 hash.
"""

import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings, get_settings
from app.db import get_db
from app.models import AuthSession, Role, User, utcnow

COOKIE_NAME = "warranty_session"
# Renew once the expiry is more than this far short of a full TTL, so an
# active user's session never runs out, without a database write on every request.
RENEW_AFTER = timedelta(days=1)


# --- Tokens and the cookie ---------------------------------------------------


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _session_ttl(settings: Settings) -> timedelta:
    return timedelta(days=settings.SESSION_TTL_DAYS)


def start_session(db: Session, user: User, settings: Settings) -> str:
    """Create a session row for `user` and return the raw token (for the cookie).

    The caller commits.
    """
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user=user,
            token_hash=hash_token(token),
            expires_at=utcnow() + _session_ttl(settings),
        )
    )
    return token


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(_session_ttl(settings).total_seconds()),
        httponly=True,  # page JavaScript can't read it
        samesite="lax",  # not sent on cross-site POSTs
        secure=settings.SESSION_COOKIE_SECURE,  # false in v1: the iPhone uses plain HTTP
        path="/",
    )


# --- The current user ----------------------------------------------------------


def get_current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """FastAPI dependency: the signed-in user, or 401."""
    not_signed_in = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise not_signed_in
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    now = utcnow()
    if session is None or session.expires_at <= now:
        raise not_signed_in

    full_expiry = now + _session_ttl(settings)
    if full_expiry - session.expires_at > RENEW_AFTER:
        session.expires_at = full_expiry
        db.commit()
        # FastAPI copies cookies set on this `response` onto the route's response.
        set_session_cookie(response, token, settings)

    return session.user


def require_reviewer(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.reviewer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Reviewers only")
    return user


def require_tech(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.tech:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Techs only")
    return user


# --- Origin check ----------------------------------------------------------------

UNSAFE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Refuse writes sent from another site's page.

    Browsers add an Origin header to cross-site POST/PATCH/PUT/DELETE requests,
    and a page can't fake it. Requests with no Origin header (curl, tests) pass:
    they don't carry a victim's cookie by accident.
    """

    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in UNSAFE_METHODS
            and origin is not None
            and origin not in self.allowed_origins
        ):
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        return await call_next(request)


# --- Routes ------------------------------------------------------------------------

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SessionCreate(BaseModel):
    name: Name
    role: Role
    email: EmailStr | None = None


class MeUpdate(BaseModel):
    """Only the fields that are sent are changed. `"email": null` clears the email."""

    name: Name | None = None
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def _name_cannot_be_cleared(cls, name: str | None) -> str:
        # Runs only when "name" is sent; leaving it out is fine.
        if name is None:
            raise ValueError("name can't be empty")
        return name


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: Role
    email: str | None


router = APIRouter(prefix="/api")


@router.post("/session", status_code=status.HTTP_201_CREATED, response_model=MeOut)
def create_session(
    body: SessionCreate,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """The role picker: a new user and a session for them."""
    user = User(name=body.name, role=body.role, email=body.email)
    token = start_session(db, user, settings)
    db.commit()
    set_session_cookie(response, token, settings)
    return user


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def end_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Sign out. Succeeds even when already signed out."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )


@router.get("/me", response_model=MeOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=MeOut)
def update_me(
    body: MeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    return user
