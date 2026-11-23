from app.models import ClaimStatus
from app.photos.labels import DAMAGE_LABELS


def ids(response):
    return [c["id"] for c in response.json()["items"]]


def test_tech_sees_only_own_claims_reviewer_sees_all(
    tech, tech_client, reviewer_client, make_user, make_claim
):
    mine, other = make_claim(tech), make_claim(make_user(name="Other Tech"))
    assert ids(tech_client.get("/api/claims")) == [mine.id]
    assert set(ids(reviewer_client.get("/api/claims"))) == {mine.id, other.id}


def test_tech_gets_404_for_someone_elses_claim(tech_client, reviewer_client, make_user, make_claim):
    other = make_claim(make_user(name="Other Tech"))
    assert tech_client.get(f"/api/claims/{other.id}").status_code == 404
    assert reviewer_client.get(f"/api/claims/{other.id}").status_code == 200


def test_search_matches_name_vin_and_claim_number(tech, reviewer_client, make_claim):
    a = make_claim(tech, claim_number="AUTH-51")
    b = make_claim(
        tech, customer_first_name="Raj", customer_last_name="Patel", vin="11111111111111111"
    )
    for q, expected in [
        ("smith", [a.id]),
        ("smi", [a.id]),  # contains, not just ends with
        ("jane smith", [a.id]),
        ("042788", [a.id]),
        ("auth-51", [a.id]),
        ("patel", [b.id]),
    ]:
        assert ids(reviewer_client.get("/api/claims", params={"q": q})) == expected


def test_search_treats_percent_and_underscore_literally(tech, reviewer_client, make_claim):
    # In a LIKE pattern, _ means "any one character" and % means "any run of characters".
    # escape_like() makes each one match only itself.
    make_claim(tech, claim_number="AUTH-51")
    underscore = make_claim(tech, claim_number="AUTH_52")
    for q, expected in [
        ("auth_5", [underscore.id]),  # unescaped, _ would also match the dash in AUTH-51
        ("%", []),  # unescaped, % would match every claim
    ]:
        assert ids(reviewer_client.get("/api/claims", params={"q": q})) == expected


def test_tech_search_finds_only_their_own_claims(tech, tech_client, make_user, make_claim):
    mine = make_claim(tech)
    make_claim(make_user(name="Other Tech"))
    assert ids(tech_client.get("/api/claims", params={"q": "smith"})) == [mine.id]


def test_status_filter(tech, reviewer_client, make_claim, db):
    make_claim(tech)
    b = make_claim(tech)
    b.status = ClaimStatus.approved
    db.flush()
    assert ids(reviewer_client.get("/api/claims", params={"status": "approved"})) == [b.id]


def test_pagination_newest_first(tech, reviewer_client, make_claim):
    c1, c2, c3 = make_claim(tech), make_claim(tech), make_claim(tech)
    page1 = reviewer_client.get("/api/claims", params={"limit": 2, "page": 1}).json()
    page2 = reviewer_client.get("/api/claims", params={"limit": 2, "page": 2}).json()
    assert [c["id"] for c in page1["items"]] == [c3.id, c2.id] and page1["total"] == 3
    assert [c["id"] for c in page2["items"]] == [c1.id]


def test_form_options(tech, tech_client, make_claim):
    # "Cna National" is filed first, so it's the spelling shown. It sorts between the
    # other two spellings, so MIN() or MAX() can't pick it by luck.
    # Fidelity and Assurant tie at one claim each, and are filed in reverse
    # alphabetical order, so only the alphabetical tiebreak puts Assurant first.
    for name in ["Cna National", "Fidelity", "CNA National", "Assurant", "cna national"]:
        make_claim(tech, warranty_company=name)
    body = tech_client.get("/api/options").json()
    assert body["damage_labels"] == list(DAMAGE_LABELS)
    assert body["warranty_companies"] == ["Cna National", "Assurant", "Fidelity"]
