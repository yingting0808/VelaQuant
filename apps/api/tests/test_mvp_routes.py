from fastapi.testclient import TestClient

from app.main import create_app


def test_mvp_dashboard_route_returns_portfolio_alerts_and_ai_prompts():
    client = TestClient(create_app())

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["name"] == "Main Book"
    assert payload["alerts"][0]["ticker"] == "AAPL"
    assert "Find portfolio risks" in payload["ai_prompts"]


def test_mvp_research_route_returns_structured_ai_result():
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/research",
        json={"ticker": " AAPL ", "question": " What changed? "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["status"] == "complete"
    assert payload["trade_plan_draft"]["requires_human_review"] is True


def test_mvp_research_route_rejects_whitespace_only_ticker():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/research",
        json={"ticker": "   ", "question": "What changed?"},
    )

    assert response.status_code == 422


def test_mvp_research_route_rejects_whitespace_only_question():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/research",
        json={"ticker": "AAPL", "question": "   "},
    )

    assert response.status_code == 422
