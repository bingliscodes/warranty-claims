from fastapi.testclient import TestClient

from app.main import create_app


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_database_down(settings):
    down = settings.model_copy(
        update={"DATABASE_URL": "postgresql+psycopg://warranty:warranty@127.0.0.1:1/warranty"}
    )
    response = TestClient(create_app(down)).get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
