import pytest


def test_tech_and_reviewer_exchange_messages(tech, tech_client, reviewer_client, make_claim):
    claim = make_claim(tech)
    url = f"/api/claims/{claim.id}/conversations"
    assert tech_client.post(url, json={"contents": "RF photos attached"}).status_code == 201
    reviewer_client.post(url, json={"contents": "Need a closer shot"})
    thread = tech_client.get(url).json()
    assert [(m["sender"]["role"], m["contents"]) for m in thread] == [
        ("tech", "RF photos attached"),
        ("reviewer", "Need a closer shot"),
    ]


def test_after_id_returns_only_newer(tech, tech_client, make_claim):
    url = f"/api/claims/{make_claim(tech).id}/conversations"
    first = tech_client.post(url, json={"contents": "one"}).json()
    tech_client.post(url, json={"contents": "two"})
    newer = tech_client.get(url, params={"after_id": first["id"]}).json()
    assert [m["contents"] for m in newer] == ["two"]


@pytest.mark.parametrize("contents", ["   ", "x" * 4001])
def test_message_length_rules(tech, tech_client, make_claim, contents):
    url = f"/api/claims/{make_claim(tech).id}/conversations"
    assert tech_client.post(url, json={"contents": contents}).status_code == 422


def test_other_tech_cannot_read_or_post(tech, make_claim, make_user, client_for):
    url = f"/api/claims/{make_claim(tech).id}/conversations"
    other = client_for(make_user(name="Other Tech"))
    assert other.get(url).status_code == 404
    assert other.post(url, json={"contents": "hi"}).status_code == 404
