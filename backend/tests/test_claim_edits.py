import pytest


def test_reviewer_updates_claim(tech, reviewer_client, make_claim):
    claim = make_claim(tech)
    r = reviewer_client.patch(
        f"/api/claims/{claim.id}",
        json={"claim_number": "AUTH-51", "status": "approved", "warranty_company": "CNA National"},
    )
    assert r.status_code == 200
    body = r.json()
    assert (body["claim_number"], body["status"], body["warranty_company"]) == (
        "AUTH-51",
        "approved",
        "CNA National",
    )


def test_claim_number_can_be_cleared(tech, reviewer_client, make_claim):
    claim = make_claim(tech, claim_number="AUTH-51")
    r = reviewer_client.patch(f"/api/claims/{claim.id}", json={"claim_number": None})
    assert r.json()["claim_number"] is None


def test_form_data_replaced_and_validated(tech, reviewer_client, make_claim, claim_payload):
    claim = make_claim(tech)
    form = claim_payload(tech)["form_data"] | {"contract_number": "C-77"}
    r = reviewer_client.patch(f"/api/claims/{claim.id}", json={"form_data": form})
    assert r.json()["form_data"]["contract_number"] == "C-77"
    bad_zip = form | {"customer_zip": "1"}
    r = reviewer_client.patch(f"/api/claims/{claim.id}", json={"form_data": bad_zip})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"vin": "BAD"},
        {"warranty_company": ""},
        {"customer_last_name": None},  # only claim_number can be cleared
        {"submission_tz": "America/Chicago"},  # not editable (design §12)
    ],
)
def test_patch_rejects_invalid_values(tech, reviewer_client, make_claim, body):
    claim = make_claim(tech)
    assert reviewer_client.patch(f"/api/claims/{claim.id}", json=body).status_code == 422


def test_tech_cannot_edit_after_submission(tech, tech_client, make_claim):
    claim = make_claim(tech)
    assert (
        tech_client.patch(f"/api/claims/{claim.id}", json={"claim_number": "X"}).status_code == 403
    )
