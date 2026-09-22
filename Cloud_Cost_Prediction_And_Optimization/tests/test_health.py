from app.api.routes.health import health_check


def test_health_endpoint():
    # Call the handler directly so the startup database hook is not invoked.
    response = health_check()
    assert response.status == "ok"