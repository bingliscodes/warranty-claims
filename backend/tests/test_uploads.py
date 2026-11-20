import base64
import json


def test_upload_url_for_jpeg(tech_client, tech, storage):
    r = tech_client.post(
        "/api/uploads", json={"content_type": "image/jpeg", "filename": "IMG_0001.jpg"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["key"].startswith(f"uploads/{tech.id}/") and body["key"].endswith(".jpg")
    assert body["fields"]["Content-Type"] == "image/jpeg" and "policy" in body["fields"]


def test_png_gets_png_extension(tech_client, storage):
    r = tech_client.post("/api/uploads", json={"content_type": "image/png", "filename": "a.png"})
    assert r.json()["key"].endswith(".png")


def test_heic_rejected(tech_client, storage):
    assert (
        tech_client.post(
            "/api/uploads", json={"content_type": "image/heic", "filename": "a.heic"}
        ).status_code
        == 422
    )


def test_upload_requires_session(client, storage):
    assert (
        client.post(
            "/api/uploads", json={"content_type": "image/jpeg", "filename": "a.jpg"}
        ).status_code
        == 401
    )


def test_size_limit_in_policy(tech_client, settings, storage):
    r = tech_client.post("/api/uploads", json={"content_type": "image/jpeg", "filename": "a.jpg"})
    policy = json.loads(base64.b64decode(r.json()["fields"]["policy"]))
    assert ["content-length-range", 1, settings.MAX_UPLOAD_BYTES] in policy["conditions"]
