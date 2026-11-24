from app.models import Role


def unread(client, claim_id):
    """The claim's unread flag as this client's claims list shows it."""
    items = client.get("/api/claims").json()["items"]
    return next(c["unread"] for c in items if c["id"] == claim_id)


def say(client, claim, text="hi"):
    client.post(f"/api/claims/{claim.id}/conversations", json={"contents": text})


def test_new_claim_unread_for_reviewer_until_opened(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    assert unread(reviewer_client, claim.id) is True
    assert unread(tech_client, claim.id) is False
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    assert unread(reviewer_client, claim.id) is False


def test_reviewer_message_marks_unread_for_tech(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    say(tech_client, claim)
    assert unread(tech_client, claim.id) is False
    say(reviewer_client, claim)
    assert unread(tech_client, claim.id) is True
    tech_client.post(f"/api/claims/{claim.id}/read")
    assert unread(tech_client, claim.id) is False


def test_tech_message_or_photo_marks_unread_for_reviewer(
    tech, tech_client, reviewer_client, make_claim, put_upload
):
    claim = make_claim(tech)
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    say(tech_client, claim)
    assert unread(reviewer_client, claim.id) is True
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    photo = {"key": put_upload(tech), "kind": "damage", "description": "Wheel LF"}
    tech_client.post(f"/api/claims/{claim.id}/photos", json={"photos": [photo]})
    assert unread(reviewer_client, claim.id) is True


def test_reviewer_edits_do_not_mark_unread_for_tech(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    reviewer_client.patch(f"/api/claims/{claim.id}", json={"status": "approved"})
    assert unread(tech_client, claim.id) is False


def test_read_state_is_per_reviewer(tech, reviewer_client, make_user, make_claim, client_for):
    claim = make_claim(tech)
    second = client_for(make_user(role=Role.reviewer, name="Second Reviewer"))
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    assert unread(reviewer_client, claim.id) is False
    assert unread(second, claim.id) is True


def test_reading_again_moves_the_bookmark(tech, tech_client, reviewer_client, make_claim):
    # The first /read creates the bookmark row; this checks the update path after it.
    claim = make_claim(tech)
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    say(tech_client, claim)
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    assert unread(reviewer_client, claim.id) is False


def test_other_reviewer_message_does_not_mark_unread(
    tech, reviewer_client, make_user, make_claim, client_for
):
    # Design §10: for a reviewer, only the tech's messages count.
    claim = make_claim(tech)
    reviewer_client.post(f"/api/claims/{claim.id}/read")
    second = client_for(make_user(role=Role.reviewer, name="Second Reviewer"))
    say(second, claim)
    assert unread(reviewer_client, claim.id) is False


def test_claim_detail_carries_unread(tech, reviewer_client, make_claim):
    assert reviewer_client.get(f"/api/claims/{make_claim(tech).id}").json()["unread"] is True


def test_edit_response_carries_unread(tech, reviewer_client, make_claim):
    # Design §10 (2026-11-24): PATCH fills in the real value too, not a default of false.
    claim = make_claim(tech)
    response = reviewer_client.patch(f"/api/claims/{claim.id}", json={"status": "approved"})
    assert response.json()["unread"] is True
