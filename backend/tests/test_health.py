from fastapi.testclient import TestClient

from burnrate.main import create_app


def test_healthcheck_returns_service_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "burnrate-backend"

