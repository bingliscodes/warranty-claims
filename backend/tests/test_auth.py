import hashlib
from datetime import timedelta

from fastapi import Depends

from app.auth import require_reviewer
from app.models import AuthSession, utcnow


def test_role_picker_creates_user_and_session(client):
    r = client.post("/api/session", json={"name": "Tess Tech", "role": "tech"})
    assert r.status_code == 201
    assert r.json()["role"] == "tech" and r.json()["email"] is None
    assert client.get("/api/me").json()["name"] == "Tess Tech"


def test_session_cookie_flags(client):
    cookie = client.post("/api/session", json={"name": "Tess", "role": "tech"}).headers["set-cookie"]
    assert "warranty_session=" in cookie and "HttpOnly" in cookie
    assert "Max-Age=31536000" in cookie and "samesite=lax" in cookie.lower()


def test_reviewer_with_email(client):
    r = client.post(
        "/api/session", json={"name": "Kim", "role": "reviewer", "email": "kim@example.com"}
    )
    assert r.status_code == 201 and r.json()["email"] == "kim@example.com"


def test_bad_email_and_blank_name_rejected(client):
    bad_email = {"name": "Kim", "role": "reviewer", "email": "nope"}
    assert client.post("/api/session", json=bad_email).status_code == 422
    assert client.post("/api/session", json={"name": "  ", "role": "tech"}).status_code == 422


def test_token_stored_only_as_hash(client, db):
    client.post("/api/session", json={"name": "Tess", "role": "tech"})
    token = client.cookies["warranty_session"]
    assert db.query(AuthSession).one().token_hash == hashlib.sha256(token.encode()).hexdigest()


def test_me_requires_a_known_session(client):
    assert client.get("/api/me").status_code == 401
    client.cookies.set("warranty_session", "made-up")
    assert client.get("/api/me").status_code == 401


def test_expired_session_rejected(db, tech, client_for):
    c = client_for(tech)
    db.query(AuthSession).update({"expires_at": utcnow() - timedelta(minutes=1)})
    assert c.get("/api/me").status_code == 401


def test_session_renewed_after_a_day(db, tech, client_for):
    c = client_for(tech)
    db.query(AuthSession).update({"expires_at": utcnow() + timedelta(days=300)})
    assert "warranty_session=" in c.get("/api/me").headers.get("set-cookie", "")
    assert db.query(AuthSession).one().expires_at > utcnow() + timedelta(days=364)


def test_update_me(tech_client):
    r = tech_client.patch("/api/me", json={"name": "Tess T", "email": "tess@example.com"})
    assert (r.json()["name"], r.json()["email"]) == ("Tess T", "tess@example.com")


def test_end_session(tech_client):
    assert tech_client.delete("/api/session").status_code == 204
    assert tech_client.get("/api/me").status_code == 401


def test_role_guard(app, tech_client, reviewer_client):
    app.add_api_route(
        "/api/test-reviewer-only", lambda user=Depends(require_reviewer): {"ok": True}
    )
    assert tech_client.get("/api/test-reviewer-only").status_code == 403
    assert reviewer_client.get("/api/test-reviewer-only").status_code == 200


def test_cross_origin_writes_rejected(client):
    body = {"name": "Tess", "role": "tech"}
    evil = client.post("/api/session", json=body, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    ours = client.post("/api/session", json=body, headers={"Origin": "http://localhost:5173"})
    assert ours.status_code == 201


def test_update_me_cannot_clear_name(tech_client):
    assert tech_client.patch("/api/me", json={"name": None}).status_code == 422
