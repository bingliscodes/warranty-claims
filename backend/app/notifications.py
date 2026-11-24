import logging
import smtplib
from collections.abc import Callable
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Claim, Role, User
from app.photos.naming import upper_segment

logger = logging.getLogger(__name__)


def build_new_claim_email(*, claim: Claim, recipient: str, settings: Settings) -> EmailMessage:
    """The "new claim" email for one reviewer.

    Only the last name, the last 8 of the VIN and a link: no phone or address (CLAUDE.md).
    The subject goes through upper_segment, so a stray newline in a name can't break it.
    """
    last_name = claim.customer_last_name
    vin8 = claim.vin[-8:]
    message = EmailMessage()
    message["From"] = settings.MAIL_FROM
    message["To"] = recipient
    message["Subject"] = f"New warranty claim: {upper_segment(last_name)} {vin8}"
    message.set_content(
        f"{claim.owner.name} submitted a new warranty claim.\n"
        f"\n"
        f"Customer last name: {last_name}\n"
        f"VIN (last 8): {vin8}\n"
        f"\n"
        f"Open it: {settings.APP_BASE_URL.rstrip('/')}/claims/{claim.id}\n"
    )
    return message


def send_email(message: EmailMessage, settings: Settings) -> None:
    """Send one message through the configured SMTP server (Mailpit in development)."""
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
        smtp.send_message(message)


def notify_reviewers_of_new_claim(
    claim_id: int, session_factory: Callable[[], Session], settings: Settings
) -> None:
    """Email every reviewer who has an email address about a newly submitted claim.

    Runs as a background task, after the tech's response has been sent. A failed send is
    logged and doesn't stop the emails to the other reviewers.
    """
    with session_factory() as db:
        claim = db.get(Claim, claim_id)
        stmt = select(User.email).where(User.email.is_not(None), User.role == Role.reviewer)
        emails = db.scalars(stmt).all()
        for email in emails:
            try:
                message = build_new_claim_email(claim=claim, recipient=email, settings=settings)
                send_email(message, settings)
            except Exception:
                logger.exception("Failed to send new-claim email for claim %s", claim_id)
