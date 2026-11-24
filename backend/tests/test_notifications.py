import smtplib
from email.message import EmailMessage

from app.models import Role
from app.notifications import build_new_claim_email, send_email


def test_submission_emails_reviewers_with_an_email(
    tech, tech_client, claim_payload, reviewer, make_user, outbox
):
    make_user(role=Role.reviewer, name="No Email Reviewer")
    make_user(role=Role.tech, name="Emailed Tech", email="tech@example.com")
    claim_id = tech_client.post("/api/claims", json=claim_payload(tech)).json()["id"]
    assert [m["To"] for m in outbox] == ["kim@example.com"]
    assert outbox[0]["Subject"] == "New warranty claim: SMITH KP042788"
    body = outbox[0].get_content()
    assert f"http://app.test/claims/{claim_id}" in body
    for private in ["6085550134", "100 Main St", "Cary", "27519"]:
        assert private not in body


def test_link_uses_configured_base_url(tech, make_claim, settings):
    claim = make_claim(tech)
    message = build_new_claim_email(
        claim=claim,
        recipient="kim@example.com",
        settings=settings.model_copy(update={"APP_BASE_URL": "http://192.168.1.50:5173"}),
    )
    assert f"http://192.168.1.50:5173/claims/{claim.id}" in message.get_content()


def test_smtp_failure_does_not_block_submission_or_other_emails(
    tech, tech_client, claim_payload, reviewer, make_user, monkeypatch, caplog
):
    make_user(role=Role.reviewer, name="Second Reviewer", email="second@example.com")
    attempts = []

    def fail_the_first_send(message, settings):
        attempts.append(message["To"])
        if len(attempts) == 1:
            raise OSError("smtp down")

    monkeypatch.setattr("app.notifications.send_email", fail_the_first_send)
    assert tech_client.post("/api/claims", json=claim_payload(tech)).status_code == 201
    assert "Failed to send new-claim email" in caplog.text
    assert sorted(attempts) == ["kim@example.com", "second@example.com"]


def test_send_email_uses_smtp_settings(monkeypatch, settings):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, message):
            calls.append(("send", message["To"]))

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    message = EmailMessage()
    message["To"] = "kim@example.com"
    send_email(
        message,
        settings.model_copy(
            update={
                "SMTP_HOST": "mail.test",
                "SMTP_PORT": 1025,
                "SMTP_STARTTLS": False,
                "SMTP_USERNAME": None,
            }
        ),
    )
    assert calls == [("connect", "mail.test", 1025), ("send", "kim@example.com")]
