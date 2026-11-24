"""Unread markers (design §10): which claims have something new for a user since they last
opened them, and the route that moves their bookmark."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy import Select, and_, func, select, union
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.claims.access import get_visible_claim
from app.db import get_db
from app.models import ChatMessage, Claim, ClaimRead, Photo, Role, User

router = APIRouter(prefix="/api")


# --- Which claims are unread -------------------------------------------------------


def _page_with_bookmark(user: User, claim_ids: Sequence[int]) -> Select[tuple[int]]:
    """The page's claims, each with this user's bookmark. Every part of the unread query
    starts from this. A claim the user never opened gets NULLs for the bookmark columns."""
    return (
        select(Claim.id)
        .outerjoin(ClaimRead, and_(ClaimRead.claim_id == Claim.id, ClaimRead.user_id == user.id))
        .where(Claim.id.in_(claim_ids))
    )


def unread_claim_ids(db: Session, user: User, claim_ids: Sequence[int]) -> set[int]:
    """The claims in claim_ids that are unread for this user, found in one query.

    - tech: a message someone else sent, past their bookmark
    - reviewer: never opened, or the owner sent a message or added a photo past their
      bookmark. Another reviewer's message doesn't count.
    """
    if not claim_ids:  # an empty page, e.g. a search that found nothing
        return set()

    message_bookmark = func.coalesce(ClaimRead.last_message_id, 0)
    photo_bookmark = func.coalesce(ClaimRead.last_photo_id, 0)

    if user.role == Role.tech:
        stmt = (
            _page_with_bookmark(user, claim_ids)
            .join(
                ChatMessage,
                and_(
                    ChatMessage.claim_id == Claim.id,
                    ChatMessage.id > message_bookmark,
                    ChatMessage.sender_id != user.id,
                ),
            )
            .distinct()
        )
        return set(db.scalars(stmt))

    never_opened = _page_with_bookmark(user, claim_ids).where(ClaimRead.claim_id.is_(None))
    new_messages = _page_with_bookmark(user, claim_ids).join(
        ChatMessage,
        and_(
            ChatMessage.claim_id == Claim.id,
            ChatMessage.id > message_bookmark,
            ChatMessage.sender_id == Claim.owner_id,
        ),
    )
    new_photos = _page_with_bookmark(user, claim_ids).join(
        Photo,
        and_(
            Photo.claim_id == Claim.id,
            Photo.id > photo_bookmark,
            Photo.added_by_id == Claim.owner_id,
        ),
    )
    return set(db.scalars(union(never_opened, new_messages, new_photos)))


def fill_unread(db: Session, user: User, claims: Sequence[Claim]) -> None:
    """Set claim.unread on each claim, for ClaimSummary and ClaimDetail to read.

    unread isn't a column, so every route that returns a claim calls this first (design
    §10). A route that forgets fails loudly: the response can't be built without it.
    """
    unread = unread_claim_ids(db, user, [claim.id for claim in claims])
    for claim in claims:
        claim.unread = claim.id in unread


# --- Moving the bookmark -----------------------------------------------------------


@router.post("/claims/{claim_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    claim_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    """Move this user's bookmark to the claim's newest message and photo (0 if none).

    One INSERT ... ON CONFLICT DO UPDATE, so two calls at once (a page opening while a
    poll lands) can't both try to create the row.
    """
    claim = get_visible_claim(claim_id, user, db)  # another tech's claim is a 404
    newest_message = (
        select(func.coalesce(func.max(ChatMessage.id), 0))
        .where(ChatMessage.claim_id == claim.id)
        .scalar_subquery()
    )
    newest_photo = (
        select(func.coalesce(func.max(Photo.id), 0))
        .where(Photo.claim_id == claim.id)
        .scalar_subquery()
    )
    stmt = insert(ClaimRead).values(
        user_id=user.id,
        claim_id=claim.id,
        last_message_id=newest_message,
        last_photo_id=newest_photo,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ClaimRead.user_id, ClaimRead.claim_id],
        set_={
            "last_message_id": stmt.excluded.last_message_id,
            "last_photo_id": stmt.excluded.last_photo_id,
        },
    )
    db.execute(stmt)
    db.commit()
