from fastapi.testclient import TestClient

from app import main as app_main
from app.main import create_app


def test_health_endpoint_returns_service_status():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "velaquant-api"}


def test_lifespan_warms_openbb_before_starting_scheduler(monkeypatch):
    events: list[str] = []

    monkeypatch.setenv("AI_STOCKS_DATA_MODE", "hybrid")
    monkeypatch.setattr(app_main, "create_db_and_tables", lambda: None)
    monkeypatch.setattr(app_main, "warm_openbb_optional_provider", lambda: events.append("openbb") or True)
    monkeypatch.setattr(app_main, "start_paper_scheduler", lambda settings: events.append("scheduler"))
    monkeypatch.setattr(app_main, "shutdown_paper_scheduler", lambda: events.append("shutdown"))

    with TestClient(app_main.create_app()) as client:
        assert client.get("/health").status_code == 200

    assert events == ["openbb", "scheduler", "shutdown"]
