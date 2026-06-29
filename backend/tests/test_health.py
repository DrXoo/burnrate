from burnrate.api.routes.health import healthcheck


def test_healthcheck_returns_service_metadata() -> None:
    response = healthcheck()

    assert response["status"] == "ok"
    assert response["service"] == "burnrate-backend"
