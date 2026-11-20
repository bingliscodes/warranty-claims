from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Role(StrEnum):
    tech = "tech"
    reviewer = "reviewer"


class ClaimStatus(StrEnum):
    submitted = "submitted"
    approved = "approved"
    closed = "closed"


class PhotoKind(StrEnum):
    vin = "vin"
    mileage = "mileage"
    damage = "damage"


def utcnow() -> datetime:
    """Timestamps come from Python in UTC, never from the database server's clock."""
    return datetime.now(UTC)


def _string_enum(enum_class: type[StrEnum]) -> Enum:
    # Stored as plain VARCHAR(20), not a Postgres ENUM type, so adding a value
    # later needs no ALTER TYPE migration.
    return Enum(enum_class, native_enum=False, length=20)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(_string_enum(Role))
    email: Mapped[str | None] = mapped_column(String(254))
    # Empty until sign-in moves to Entra ID (design §6).
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = _created_at()


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship()
    # SHA-256 hex digest of the cookie token; the token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped[User] = relationship()
    status: Mapped[ClaimStatus] = mapped_column(
        _string_enum(ClaimStatus), default=ClaimStatus.submitted
    )

    # Real columns: the fields we search, sort, or build export filenames from (design §7).
    warranty_company: Mapped[str] = mapped_column(String(120))
    customer_first_name: Mapped[str] = mapped_column(String(100))
    customer_last_name: Mapped[str] = mapped_column(String(100))
    vin: Mapped[str] = mapped_column(String(17), index=True)
    claim_number: Mapped[str | None] = mapped_column(String(64))
    # IANA zone name from the tech's browser, e.g. "America/New_York".
    submission_tz: Mapped[str] = mapped_column(String(64))

    # Everything else on the form: phone, address, city, state, ZIP, year,
    # make, model, mileage, contract number (design §7).
    form_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    photos: Mapped[list[Photo]] = relationship(back_populates="claim", order_by="Photo.id")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="claim", order_by="ChatMessage.id"
    )


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"))
    claim: Mapped[Claim] = relationship(back_populates="photos")
    kind: Mapped[PhotoKind] = mapped_column(_string_enum(PhotoKind))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(200))
    excluded: Mapped[bool] = mapped_column(default=False)
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    added_by: Mapped[User] = relationship()
    created_at: Mapped[datetime] = _created_at()


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"))
    claim: Mapped[Claim] = relationship(back_populates="messages")
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender: Mapped[User] = relationship()
    contents: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class ClaimRead(Base):
    """How far one user has read one claim. IDs, not times, mark the spot:
    anything with a higher ID than these is unread."""

    __tablename__ = "claim_reads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), primary_key=True)
    last_message_id: Mapped[int] = mapped_column(default=0)
    last_photo_id: Mapped[int] = mapped_column(default=0)
