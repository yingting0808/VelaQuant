from fastapi.testclient import TestClient

from app.api.routes import mvp
from app.data.providers.openbb_optional import OpenBBOptionalProvider
from app.data.providers.registry import HybridMarketDataProvider
from app.main import create_app


class CloseTrackingSecProvider:
    def __init__(self) -> None:
        self.closed = False

    def get_research_evidence(self, ticker: str) -> list:
        return []

    def get_statuses(self) -> list:
        return []

    def close(self) -> None:
        self.closed = True


def test_mvp_dashboard_route_returns_portfolio_alerts_and_ai_prompts():
    client = TestClient(create_app())

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["name"] == "主组合"
    assert payload["alerts"][0]["ticker"] == "AAPL"
    assert "识别组合风险" in payload["ai_prompts"]


def test_mvp_dashboard_route_includes_provider_and_strategy_status():
    client = TestClient(create_app())

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])
    assert "strategy_lab" in payload


def test_mvp_dashboard_route_openbb_optional_mode_uses_mock_quote_fallback(monkeypatch):
    monkeypatch.setenv("AI_STOCKS_DATA_MODE", "openbb_optional")
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_mode"] == "openbb_optional"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])
    assert any(source["name"] == "OpenBB" for source in payload["data_sources"])


def test_mvp_data_sources_status_route_returns_statuses():
    client = TestClient(create_app())

    response = client.get("/api/mvp/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])


def test_mvp_dashboard_route_closes_market_data_provider(monkeypatch):
    sec_provider = CloseTrackingSecProvider()
    provider = HybridMarketDataProvider(
        sec_provider=sec_provider,
        openbb_provider=OpenBBOptionalProvider(module_finder=lambda _: None),
    )

    def build_test_provider(settings):
        return provider

    monkeypatch.setattr(mvp, "build_market_data_provider", build_test_provider)
    client = TestClient(create_app())

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    assert sec_provider.closed is True


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


def test_mvp_research_cors_preflight_allows_loopback_web_origin():
    client = TestClient(create_app())

    response = client.options(
        "/api/mvp/research",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
