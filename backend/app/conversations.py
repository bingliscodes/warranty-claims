"""A claim's chat thread (design §10). The open claim page polls GET for new messages."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.claims.access import get_visible_claim
from app.claims.schemas import MessageIn, MessageOut
from app.db import get_db
from app.models import ChatMessage, User

router = APIRouter(prefix="/api/claims/{claim_id}/conversations")


def messages_after(db: Session, claim_id: int, after_id: int) -> list[ChatMessage]:
    """The claim's messages with an ID above after_id, oldest first.

    after_id is the newest message the page already shows (0 for none). A server-sent
    events stream would reuse this, if polling is ever replaced.
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.claim_id == claim_id, ChatMessage.id > after_id)
        .order_by(ChatMessage.id)
    )
    return list(db.scalars(stmt))


@router.get("", response_model=list[MessageOut])
def list_messages(
    claim_id: int,
    after_id: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    claim = get_visible_claim(claim_id, user, db)  # another tech's claim is a 404
    return messages_after(db, claim.id, after_id)


@router.post("", status_code=201, response_model=MessageOut)
def send_message(
    claim_id: int,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessage:
    claim = get_visible_claim(claim_id, user, db)
    new_message = ChatMessage(claim=claim, sender=user, contents=body.contents)
    db.add(new_message)
    db.commit()
    return new_message
