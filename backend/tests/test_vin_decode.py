import httpx
import pytest

from app.vin_decode import get_vpic_client

SAMPLE_VIN = "1M8GDM9AXKP042788"


@pytest.fixture
def vpic(app):
    """A fake vPIC. Set vpic["handler"] to decide its answer; vpic["requests"] lists the calls."""
    state = {"requests": [], "handler": None}

    def route(request):
        state["requests"].append(request)
        return state["handler"](request)

    app.dependency_overrides[get_vpic_client] = lambda: httpx.Client(
        transport=httpx.MockTransport(route)
    )
    return state


def results(**values):
    """A vPIC answer with every field blank except the ones given."""
    return httpx.Response(
        200, json={"Results": [{"ModelYear": "", "Make": "", "Model": "", **values}]}
    )


def timeout(request):
    raise httpx.ReadTimeout("slow", request=request)


def test_decodes_year_make_model(tech_client, vpic):
    vpic["handler"] = lambda r: results(ModelYear="2024", Make="HONDA", Model="Civic")
    assert tech_client.get(f"/api/vin/{SAMPLE_VIN}/decode").json() == {
        "year": 2024,
        "make": "HONDA",
        "model": "Civic",
    }
    sent = vpic["requests"][0]
    assert sent.url.path == f"/api/vehicles/DecodeVinValues/{SAMPLE_VIN}"
    assert sent.url.params["format"] == "json"


def test_blank_values_become_null(tech_client, vpic):
    vpic["handler"] = lambda r: results()
    assert tech_client.get(f"/api/vin/{SAMPLE_VIN}/decode").json() == {
        "year": None,
        "make": None,
        "model": None,
    }


@pytest.mark.parametrize("handler", [lambda r: httpx.Response(500), timeout])
def test_upstream_failure_is_503(tech_client, vpic, handler, caplog):
    vpic["handler"] = handler
    response = tech_client.get(f"/api/vin/{SAMPLE_VIN}/decode")
    assert response.status_code == 503
    assert response.json() == {"detail": "VIN lookup unavailable"}
    assert "VIN lookup failed" in caplog.text


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, text="<html>Down for maintenance</html>"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"Results": []}),
        results(ModelYear=None),
    ],
    ids=["not-json", "no-results", "empty-results", "null-year"],
)
def test_unreadable_answer_is_503(tech_client, vpic, answer):
    vpic["handler"] = lambda r: answer
    assert tech_client.get(f"/api/vin/{SAMPLE_VIN}/decode").status_code == 503


def test_invalid_vin_rejected_without_lookup(tech_client, vpic):
    assert tech_client.get("/api/vin/ABC/decode").status_code == 422
    assert vpic["requests"] == []


def test_requires_session(client, vpic):
    assert client.get(f"/api/vin/{SAMPLE_VIN}/decode").status_code == 401
