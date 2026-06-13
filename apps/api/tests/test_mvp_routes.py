from fastapi.testclient import TestClient
import pytest

from app.api.routes import mvp
from app.data.providers.base import ProviderStatus
from app.data.providers.openbb_optional import OpenBBOptionalProvider
from app.data.providers import registry
from app.data.providers.registry import HybridMarketDataProvider
from app.main import create_app
from app.services import strategy_catalog
from app.services.lean_backtest import BacktestHistoryItem, BacktestResult, BacktestStatistics
from app.services.paper_trading import (
    PaperAccountPayload,
    PaperCandidatePayload,
    PaperOrderCreate,
    PaperOrderPayload,
    PaperReviewPayload,
    PaperRunPayload,
    PaperTradingSummary,
)
from app.services.research_notebook import ResearchNoteCreate, ResearchNotePayload
from app.services.strategy_catalog import StrategyDefinition, StrategyParameterDefinition
from app.services.strategy_evaluation import StrategyEvaluationPayload, StrategyEvaluationReadiness
from app.services.strategy_attribution import (
    AttributionComponent,
    DrawdownContributor,
    DrawdownAttribution,
    ExpectancyDecomposition,
    MarketRegimeAttribution,
    RegimeBreakdownPayload,
    RegimePerformanceItem,
    SignalQualityAttribution,
    SignalDecayAttribution,
    StrategyAttributionPayload,
    TickerSignalAttribution,
)
from app.services.strategy_lab import StrategyLabStatus, StrategyToolStatus
from app.services.strategy_registry import StrategyRegistryEntry, StrategyRegistryPayload
from app.services.workspace import (
    NoteCreate,
    NotePayload,
    PortfolioPayload,
    PositionImportPayload,
    PositionPayload,
    PositionUpsert,
    WatchlistItemPayload,
    WatchlistUpsert,
    WorkspaceSummary,
)


FAKE_STRATEGY_LAB_PAYLOAD = {
    "can_run_backtests": True,
    "summary": "Strategy Lab test readiness.",
    "tools": [
        {
            "name": "Docker CLI",
            "available": True,
            "version": "Docker version test",
            "message": "Docker CLI is available.",
        }
    ],
}


@pytest.fixture(autouse=True)
def stub_strategy_lab_status(monkeypatch):
    def fake_strategy_lab_status() -> StrategyLabStatus:
        return StrategyLabStatus(
            can_run_backtests=FAKE_STRATEGY_LAB_PAYLOAD["can_run_backtests"],
            summary=FAKE_STRATEGY_LAB_PAYLOAD["summary"],
            tools=[StrategyToolStatus(**tool) for tool in FAKE_STRATEGY_LAB_PAYLOAD["tools"]],
        )

    monkeypatch.setattr(mvp, "get_strategy_lab_status", fake_strategy_lab_status)


class CloseTrackingSecProvider:
    def __init__(self) -> None:
        self.closed = False

    def get_research_evidence(self, ticker: str) -> list:
        return []

    def get_statuses(self) -> list:
        return []

    def close(self) -> None:
        self.closed = True


class EmptySecProvider:
    def __init__(self, **kwargs) -> None:
        self.closed = False

    def get_research_evidence(self, ticker: str) -> list:
        return []

    def get_statuses(self) -> list[ProviderStatus]:
        return [
            ProviderStatus(
                name="SEC EDGAR",
                mode="sec_edgar",
                available=True,
                message="fixture",
                checked_at="2026-06-12T00:00:00Z",
                version="fixture",
            )
        ]

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
    assert payload["strategy_lab"] == FAKE_STRATEGY_LAB_PAYLOAD


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


def test_mvp_strategy_lab_status_route_returns_readiness_payload():
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/status")

    assert response.status_code == 200
    assert response.json() == FAKE_STRATEGY_LAB_PAYLOAD


def test_mvp_strategy_lab_evaluation_route_returns_alpha_report(monkeypatch):
    evaluation = StrategyEvaluationPayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        sample_size=21,
        filled_order_count=21,
        rejected_order_count=1,
        closed_trade_count=5,
        signal_precision=0.7143,
        expectancy=4.2,
        max_drawdown=0.08,
        stability_score=0.69,
        readiness=StrategyEvaluationReadiness.watch,
        promotion_gate="keep_paper_running",
        event_chain_count=80,
        notes="继续观察。",
    )

    monkeypatch.setattr(mvp, "evaluate_current_paper_strategy", lambda session: evaluation, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/evaluation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "deterministic_watchlist_v1"
    assert payload["readiness"] == "watch"
    assert payload["promotion_gate"] == "keep_paper_running"


def test_mvp_strategy_lab_attribution_route_returns_explanation_report(monkeypatch):
    attribution = StrategyAttributionPayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        signal_quality=SignalQualityAttribution(
            market_event_count=12,
            trade_intent_count=6,
            actionable_signal_rate=0.5,
            average_confidence=0.72,
            false_positive_rate=0.25,
        ),
        expectancy_decomposition=ExpectancyDecomposition(
            realized_pnl=80,
            unrealized_pnl=-20,
            closed_trade_component=80,
            open_trade_component=-20,
            total_observed_pnl=60,
            components=[
                AttributionComponent(name="trend_component", value=0, basis="proxy"),
                AttributionComponent(name="volatility_component", value=0, basis="proxy"),
                AttributionComponent(name="timing_component", value=-20, basis="proxy"),
                AttributionComponent(name="risk_component", value=-1, basis="proxy"),
                AttributionComponent(name="noise_component", value=-20, basis="proxy"),
            ],
        ),
        ticker_diagnostics=[
            TickerSignalAttribution(
                ticker="NVDA",
                market_event_count=8,
                trade_intent_count=4,
                filled_order_count=3,
                false_positive_count=1,
                false_positive_rate=0.3333,
                average_confidence=0.74,
                realized_pnl=80,
                unrealized_pnl=-20,
                observed_pnl=60,
            )
        ],
        signal_decay=SignalDecayAttribution(
            threshold_days=5,
            open_position_count=2,
            stale_open_position_count=1,
            stale_tickers=["NVDA"],
            average_holding_days=6.5,
            basis="proxy",
        ),
        regime=MarketRegimeAttribution(
            regime="drawdown_pressure",
            basis="复盘权益曲线从峰值回撤超过 10%。",
            review_count=5,
            equity_change=-0.04,
        ),
        regime_breakdown=RegimeBreakdownPayload(
            primary_regime="trend_market",
            items=[
                RegimePerformanceItem(
                    regime="trend_market",
                    ticker_count=1,
                    observed_pnl=60,
                    average_return=0.08,
                    average_volatility=0.01,
                    sample_count=2,
                    sharpe_proxy=3.2,
                    tickers=["NVDA"],
                    basis="proxy",
                ),
                RegimePerformanceItem(
                    regime="range_market",
                    ticker_count=0,
                    observed_pnl=0,
                    average_return=0,
                    average_volatility=0,
                    sample_count=0,
                    sharpe_proxy=0,
                    tickers=[],
                    basis="proxy",
                ),
                RegimePerformanceItem(
                    regime="high_volatility",
                    ticker_count=0,
                    observed_pnl=0,
                    average_return=0,
                    average_volatility=0,
                    sample_count=0,
                    sharpe_proxy=0,
                    tickers=[],
                    basis="proxy",
                ),
                RegimePerformanceItem(
                    regime="insufficient_data",
                    ticker_count=0,
                    observed_pnl=0,
                    average_return=0,
                    average_volatility=0,
                    sample_count=0,
                    sharpe_proxy=0,
                    tickers=[],
                    basis="proxy",
                ),
            ],
            basis="proxy",
        ),
        drawdown=DrawdownAttribution(
            source="open_position_pressure",
            max_drawdown=0.1161,
            basis="开放头寸浮亏。",
            contributors=[
                DrawdownContributor(name="market_driven", value=0.1161, basis="proxy"),
                DrawdownContributor(name="signal_failure", value=-20, basis="proxy"),
                DrawdownContributor(name="execution_lag", value=0, basis="proxy"),
                DrawdownContributor(name="risk_overreach", value=1, basis="proxy"),
            ],
        ),
        data_quality_warnings=["market_regime_is_proxy"],
        summary="归因测试。",
    )

    captured = {}

    def fake_attribution(session, provider=None):
        captured["provider"] = provider
        return attribution

    monkeypatch.setattr(mvp, "attribute_current_paper_strategy", fake_attribution, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/attribution")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "deterministic_watchlist_v1"
    assert payload["signal_quality"]["actionable_signal_rate"] == 0.5
    assert payload["ticker_diagnostics"][0]["ticker"] == "NVDA"
    assert payload["signal_decay"]["stale_tickers"] == ["NVDA"]
    assert payload["expectancy_decomposition"]["total_observed_pnl"] == 60
    component_names = {item["name"] for item in payload["expectancy_decomposition"]["components"]}
    assert "volatility_component" in component_names
    assert "timing_component" in component_names
    assert payload["regime"]["regime"] == "drawdown_pressure"
    assert payload["regime_breakdown"]["primary_regime"] == "trend_market"
    assert payload["regime_breakdown"]["items"][0]["sample_count"] == 2
    assert payload["regime_breakdown"]["items"][0]["sharpe_proxy"] == 3.2
    assert payload["regime_breakdown"]["items"][0]["tickers"] == ["NVDA"]
    assert payload["drawdown"]["source"] == "open_position_pressure"
    assert payload["drawdown"]["contributors"][3]["name"] == "risk_overreach"
    assert captured["provider"] is not None


def test_mvp_strategy_lab_registry_route_returns_strategy_control_plane(monkeypatch):
    registry_payload = StrategyRegistryPayload(
        active_strategy_id="deterministic_watchlist_v1",
        entries=[
            StrategyRegistryEntry(
                strategy_id="deterministic_watchlist_v1",
                name="Deterministic Watchlist Strategy",
                version="v1",
                source="paper_core",
                execution_mode="paper",
                status="active",
                rank=1,
                ranking_score=74,
                readiness="watch",
                promotion_gate="keep_paper_running",
                sample_size=22,
                filled_order_count=21,
                observed_pnl=125.5,
                primary_regime="trend_market",
                signal_quality_score=0.5,
                backtest_status=None,
                supports_live=False,
                supports_hot_swap=False,
                notes="fixture",
            )
        ],
        missing_capabilities=["automatic_lifecycle_actions"],
        summary="Registry is read-only: fixture.",
    )
    captured = {}

    def fake_registry(session, provider=None):
        captured["provider"] = provider
        return registry_payload

    monkeypatch.setattr(mvp, "get_strategy_registry", fake_registry, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/registry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_strategy_id"] == "deterministic_watchlist_v1"
    assert payload["entries"][0]["ranking_score"] == 74
    assert payload["entries"][0]["supports_live"] is False
    assert payload["missing_capabilities"] == ["automatic_lifecycle_actions"]
    assert captured["provider"] is not None


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


def test_mvp_research_sec_mode_does_not_mask_missing_sec_evidence(monkeypatch):
    monkeypatch.setenv("AI_STOCKS_DATA_MODE", "sec_edgar")
    monkeypatch.setattr(registry, "SecEdgarProvider", EmptySecProvider)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/research",
        json={"ticker": "AAPL", "question": "What changed?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "insufficient_evidence"
    assert payload["evidence_count"] == 0


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


def test_trading_core_dry_run_returns_state_machine():
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/trading-core/dry-run",
        json={
            "event": {
                "source": "ai_structured",
                "event_type": "earnings",
                "ticker": "NVDA",
                "occurred_at": "2026-06-13T00:00:00Z",
                "summary": "NVDA reported stronger than expected data center revenue.",
                "sentiment": "positive",
                "confidence": 0.86,
                "impact_score": 0.74,
            },
            "portfolio": {"cash": 100000, "equity": 100000, "positions": []},
            "watchlist": ["NVDA"],
            "risk_limits": {"max_order_notional": 5000},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["orders"][0]["current_state"] == "filled"
    assert [item["state"] for item in payload["orders"][0]["state_history"]] == [
        "new",
        "validated",
        "risk_approved",
        "sent",
        "filled",
    ]
    assert [event["topic"] for event in payload["events"]] == [
        "market_event",
        "strategy_input",
        "trade_intent",
        "order_state",
    ]
    assert payload["events"][-1]["payload"]["current_state"] == "filled"


def test_mvp_market_snapshot_route_returns_quote_fundamentals_and_sources():
    client = TestClient(create_app())

    response = client.get("/api/mvp/market/snapshot/nvda")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert "quote" in payload
    assert "fundamentals" in payload
    assert "history" in payload
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])


def test_mvp_market_history_rejects_unsupported_interval():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.get("/api/mvp/market/history/AAPL?interval=5m")

    assert response.status_code == 422


def test_mvp_market_quote_normalizes_arbitrary_ticker():
    client = TestClient(create_app())

    response = client.get("/api/mvp/market/quote/tsla")

    assert response.status_code == 200
    assert response.json()["ticker"] == "TSLA"


def test_mvp_strategy_lab_strategies_route_returns_catalog(monkeypatch):
    def fake_list_strategies():
        return [
            StrategyDefinition(
                id="moving_average_cross",
                name="MovingAverageCross",
                description="fixture strategy",
                language="Python",
                asset_class="US Equity",
                default_symbol="AAPL",
                resolution="Daily",
                project_path="MovingAverageCross",
                enabled=True,
                parameters=[
                    StrategyParameterDefinition(
                        name="symbol",
                        label="Ticker",
                        kind="ticker",
                        default="AAPL",
                        required=True,
                    )
                ],
            )
        ]

    monkeypatch.setattr(mvp, "load_enabled_strategies", fake_list_strategies)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategies"][0]["id"] == "moving_average_cross"
    assert "project_path" not in payload["strategies"][0]
    assert payload["strategies"][0]["parameters"][0]["name"] == "symbol"


def test_mvp_strategy_lab_latest_backtest_route_returns_null_initially(monkeypatch):
    monkeypatch.setattr(mvp, "read_latest_backtest", lambda: None)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/backtests/latest")

    assert response.status_code == 200
    assert response.json() == {"latest": None}


def test_mvp_strategy_lab_backtest_route_returns_structured_result(monkeypatch):
    result = BacktestResult(
        run_id="20260612T101500Z-moving_average_cross",
        strategy_id="moving_average_cross",
        status="success",
        started_at="2026-06-12T10:15:00Z",
        completed_at="2026-06-12T10:16:15Z",
        duration_seconds=75.0,
        message="Backtest completed.",
        parameters={"symbol": "MSFT", "fast_period": "10", "slow_period": "30"},
        statistics=BacktestStatistics(total_net_profit="12.34%", sharpe_ratio="0.72"),
        equity=[],
        logs=["TRACE:: Backtest completed"],
        output_directory="apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross",
    )

    def fake_run(strategy_id: str, parameter_overrides: dict[str, str] | None = None) -> BacktestResult:
        assert strategy_id == "moving_average_cross"
        assert parameter_overrides == {"symbol": "MSFT", "fast_period": "10", "slow_period": "30"}
        return result

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={
            "strategy_id": "moving_average_cross",
            "parameters": {"symbol": "MSFT", "fast_period": "10", "slow_period": "30"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["parameters"]["symbol"] == "MSFT"
    assert payload["statistics"]["total_net_profit"] == "12.34%"


def test_mvp_strategy_lab_backtest_route_rejects_unknown_strategy(monkeypatch):
    def fake_run(strategy_id: str, parameter_overrides: dict[str, str] | None = None) -> BacktestResult:
        raise strategy_catalog.UnknownStrategyError("Unknown strategy_id: missing")

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "missing"},
    )

    assert response.status_code == 404


def test_mvp_strategy_lab_backtest_route_rejects_invalid_parameters(monkeypatch):
    def fake_run(strategy_id: str, parameter_overrides: dict[str, str] | None = None) -> BacktestResult:
        raise mvp.BacktestParameterValidationError("Invalid ticker parameter symbol: BAD TICKER")

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "moving_average_cross", "parameters": {"symbol": "BAD TICKER"}},
    )

    assert response.status_code == 422
    assert "Invalid ticker" in response.json()["detail"]


def test_mvp_strategy_lab_backtest_route_does_not_mask_catalog_errors(monkeypatch):
    def fake_run(strategy_id: str, parameter_overrides: dict[str, str] | None = None) -> BacktestResult:
        raise ValueError("catalog broken")

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "moving_average_cross"},
    )

    assert response.status_code == 500


def test_mvp_strategy_lab_backtest_route_rejects_blank_strategy_id():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "   "},
    )

    assert response.status_code == 422


def test_mvp_strategy_lab_backtest_history_route_returns_history(monkeypatch):
    history_item = BacktestHistoryItem(
        run_id="20260613T101500Z-moving_average_cross",
        strategy_id="moving_average_cross",
        status="success",
        started_at="2026-06-13T10:15:00Z",
        completed_at="2026-06-13T10:16:15Z",
        duration_seconds=75.0,
        parameters={"symbol": "AAPL", "fast_period": "20", "slow_period": "50"},
        statistics=BacktestStatistics(total_net_profit="12.34%", sharpe_ratio="0.72"),
    )

    def fake_history(limit: int = 10) -> list[BacktestHistoryItem]:
        assert limit == 5
        return [history_item]

    monkeypatch.setattr(mvp, "read_backtest_history", fake_history)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/backtests/history?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["history"][0]["run_id"] == history_item.run_id
    assert payload["history"][0]["parameters"]["symbol"] == "AAPL"


def test_mvp_workspace_route_returns_summary(monkeypatch):
    summary = WorkspaceSummary(
        team_id="00000000-0000-0000-0000-000000000001",
        team_name="个人工作区",
        portfolio_id="00000000-0000-0000-0000-000000000002",
        portfolio_name="主组合",
        position_count=2,
        watchlist_count=3,
        note_count=1,
    )

    monkeypatch.setattr(mvp, "get_workspace_summary", lambda session: summary, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/workspace")

    assert response.status_code == 200
    assert response.json()["portfolio_name"] == "主组合"


def test_mvp_portfolio_route_returns_workspace_portfolio(monkeypatch):
    portfolio = PortfolioPayload(
        id="00000000-0000-0000-0000-000000000002",
        name="主组合",
        base_currency="USD",
        total_market_value=1000,
        positions=[
            PositionPayload(
                id="00000000-0000-0000-0000-000000000003",
                ticker="AAPL",
                quantity=2,
                average_cost=100,
                currency="USD",
                price=120,
                market_value=240,
                weight=1,
                updated_at="2026-06-13T00:00:00Z",
            )
        ],
    )

    monkeypatch.setattr(mvp, "get_portfolio_payload", lambda session, provider: portfolio, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/portfolio")

    assert response.status_code == 200
    assert response.json()["positions"][0]["ticker"] == "AAPL"


def test_mvp_position_upsert_and_delete_routes(monkeypatch):
    saved = PositionPayload(
        id="00000000-0000-0000-0000-000000000003",
        ticker="TSLA",
        quantity=4,
        average_cost=181.25,
        currency="USD",
        price=None,
        market_value=725,
        weight=0,
        updated_at="2026-06-13T00:00:00Z",
    )

    def fake_upsert(session, data: PositionUpsert) -> PositionPayload:
        assert data.ticker == "TSLA"
        assert data.quantity == 4
        return saved

    def fake_delete(session, ticker: str) -> PositionPayload:
        assert ticker == "TSLA"
        return saved

    monkeypatch.setattr(mvp, "upsert_position", fake_upsert, raising=False)
    monkeypatch.setattr(mvp, "delete_position", fake_delete, raising=False)
    client = TestClient(create_app())

    response = client.put(
        "/api/mvp/portfolio/positions",
        json={"ticker": "tsla", "quantity": 4, "average_cost": 181.25, "currency": "usd"},
    )
    delete_response = client.delete("/api/mvp/portfolio/positions/TSLA")

    assert response.status_code == 200
    assert response.json()["ticker"] == "TSLA"
    assert delete_response.status_code == 200
    assert delete_response.json()["ticker"] == "TSLA"


def test_mvp_position_delete_route_returns_404_for_missing(monkeypatch):
    def fake_delete(session, ticker: str) -> PositionPayload:
        raise ValueError("Unknown position ticker: MISSING")

    monkeypatch.setattr(mvp, "delete_position", fake_delete, raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.delete("/api/mvp/portfolio/positions/MISSING")

    assert response.status_code == 404


def test_mvp_portfolio_import_route_returns_import_summary(monkeypatch):
    payload = PositionImportPayload(imported_count=1, errors=[], portfolio=None)

    def fake_import(session, content: str, provider=None) -> PositionImportPayload:
        assert "TSLA" in content
        return payload

    monkeypatch.setattr(mvp, "import_positions_csv", fake_import, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/portfolio/import", json={"content": "ticker,quantity,average_cost\nTSLA,2,190\n"})

    assert response.status_code == 200
    assert response.json()["imported_count"] == 1


def test_mvp_watchlist_routes(monkeypatch):
    item = WatchlistItemPayload(
        id="00000000-0000-0000-0000-000000000004",
        ticker="NVDA",
        thesis="AI 基础设施",
        created_at="2026-06-13T00:00:00Z",
    )

    def fake_upsert(session, data: WatchlistUpsert) -> WatchlistItemPayload:
        assert data.ticker == "NVDA"
        return item

    monkeypatch.setattr(mvp, "list_watchlist_items", lambda session: [item], raising=False)
    monkeypatch.setattr(mvp, "upsert_watchlist_item", fake_upsert, raising=False)
    monkeypatch.setattr(mvp, "delete_watchlist_item", lambda session, ticker: item, raising=False)
    client = TestClient(create_app())

    list_response = client.get("/api/mvp/watchlist")
    post_response = client.post("/api/mvp/watchlist", json={"ticker": "nvda", "thesis": "AI 基础设施"})
    delete_response = client.delete("/api/mvp/watchlist/NVDA")

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["ticker"] == "NVDA"
    assert post_response.status_code == 200
    assert delete_response.status_code == 200


def test_mvp_notes_routes(monkeypatch):
    note = NotePayload(
        id="00000000-0000-0000-0000-000000000005",
        ticker="AAPL",
        title="服务收入",
        body="观察利润率。",
        created_at="2026-06-13T00:00:00Z",
    )

    def fake_create(session, data: NoteCreate) -> NotePayload:
        assert data.ticker == "AAPL"
        return note

    monkeypatch.setattr(mvp, "list_notes", lambda session: [note], raising=False)
    monkeypatch.setattr(mvp, "create_note", fake_create, raising=False)
    client = TestClient(create_app())

    list_response = client.get("/api/mvp/notes")
    post_response = client.post("/api/mvp/notes", json={"ticker": "aapl", "title": "服务收入", "body": "观察利润率。"})

    assert list_response.status_code == 200
    assert list_response.json()["notes"][0]["title"] == "服务收入"
    assert post_response.status_code == 200
    assert post_response.json()["ticker"] == "AAPL"


def _research_result_payload() -> dict:
    return {
        "ticker": "AAPL",
        "status": "complete",
        "summary": "AAPL: 服务收入韧性仍在。",
        "bull_case": "服务收入支撑多头观点。",
        "bear_case": "估值压缩仍是风险。",
        "watch_items": ["复核 10-Q"],
        "evidence_count": 1,
        "trade_plan_draft": {
            "entry_condition": "人工复核后才考虑后续动作。",
            "invalidation_condition": "证据相反则失效。",
            "risk_notes": ["必须经过人工审批。"],
            "requires_human_review": True,
        },
    }


def test_mvp_research_note_route_saves_ai_result(monkeypatch):
    note = NotePayload(
        id="00000000-0000-0000-0000-000000000006",
        ticker="AAPL",
        title="AI 研究 - AAPL - 识别组合风险",
        body="AAPL: 服务收入韧性仍在。",
        created_at="2026-06-13T00:00:00Z",
    )

    def fake_save(session, data: ResearchNoteCreate) -> ResearchNotePayload:
        assert data.prompt == "识别组合风险"
        assert data.result.ticker == "AAPL"
        return ResearchNotePayload(ai_run_id="00000000-0000-0000-0000-000000000007", note=note)

    monkeypatch.setattr(mvp, "save_research_result_as_note", fake_save, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/research/notes",
        json={"prompt": "识别组合风险", "result": _research_result_payload()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_run_id"] == "00000000-0000-0000-0000-000000000007"
    assert payload["note"]["ticker"] == "AAPL"
    assert payload["note"]["title"] == "AI 研究 - AAPL - 识别组合风险"
    assert "AAPL: 服务收入韧性仍在。" in payload["note"]["body"]


def test_mvp_research_note_route_rejects_malformed_result():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/research/notes",
        json={"prompt": "识别组合风险", "result": {"ticker": "AAPL"}},
    )

    assert response.status_code == 422


def _paper_trading_summary_payload() -> PaperTradingSummary:
    return PaperTradingSummary(
        account=PaperAccountPayload(
            id="00000000-0000-0000-0000-000000000010",
            name="默认模拟盘",
            mode="paper",
            starting_cash=100000,
            cash=100000,
            realized_pnl=0,
            unrealized_pnl=0,
            equity=100000,
            updated_at="2026-06-13T00:00:00Z",
        ),
        candidates=[
            PaperCandidatePayload(
                id="00000000-0000-0000-0000-000000000011",
                ticker="NVDA",
                action="buy",
                rank=1,
                confidence=0.9,
                thesis="NVDA 候选买入：3 条证据支持继续跟踪 NVDA。",
                risk_notes="模拟结果不能直接代表实盘。",
                evidence_summary="3 条证据支持继续跟踪 NVDA",
                proposed_quantity=40,
                status="proposed",
                created_at="2026-06-13T00:00:00Z",
            )
        ],
        orders=[],
        positions=[],
        latest_review=PaperReviewPayload(
            id="00000000-0000-0000-0000-000000000012",
            trading_day="2026-06-13",
            equity=100000,
            cash=100000,
            realized_pnl=0,
            unrealized_pnl=0,
            trade_count=0,
            win_rate=0,
            average_win=0,
            average_loss=0,
            expectancy=0,
            readiness="collecting",
            notes="正在收集模拟盘样本。",
            created_at="2026-06-13T00:00:00Z",
        ),
    )


def test_mvp_paper_trading_summary_route_returns_sections(monkeypatch):
    monkeypatch.setattr(mvp, "get_paper_trading_summary", lambda session, provider: _paper_trading_summary_payload(), raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"]["name"] == "默认模拟盘"
    assert payload["account"]["mode"] == "paper"
    assert payload["candidates"][0]["ticker"] == "NVDA"
    assert payload["latest_review"]["readiness"] == "collecting"


def test_mvp_paper_trading_daily_run_route_generates_candidates(monkeypatch):
    monkeypatch.setattr(mvp, "run_daily_paper_trading_loop", lambda session, provider: _paper_trading_summary_payload(), raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/daily-run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"][0]["action"] == "buy"
    assert "证据" in payload["candidates"][0]["thesis"]


def test_mvp_paper_trading_order_route_fills_or_rejects(monkeypatch):
    order = PaperOrderPayload(
        id="00000000-0000-0000-0000-000000000013",
        ticker="NVDA",
        side="buy",
        order_type="market",
        quantity=10,
        status="filled",
        fill_price=125.75,
        realized_pnl=0,
        rejection_reason=None,
        submitted_at="2026-06-13T00:00:00Z",
        filled_at="2026-06-13T00:00:00Z",
    )

    def fake_submit(session, provider, data: PaperOrderCreate) -> PaperOrderPayload:
        assert data.ticker == "NVDA"
        assert data.side == "buy"
        if data.quantity > 100:
            raise ValueError("Insufficient paper cash for NVDA.")
        return order

    monkeypatch.setattr(mvp, "submit_paper_order", fake_submit, raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)

    fill_response = client.post(
        "/api/mvp/paper-trading/orders",
        json={"ticker": "nvda", "side": "buy", "quantity": 10, "order_type": "market"},
    )
    reject_response = client.post(
        "/api/mvp/paper-trading/orders",
        json={"ticker": "nvda", "side": "buy", "quantity": 101, "order_type": "market"},
    )

    assert fill_response.status_code == 200
    assert fill_response.json()["status"] == "filled"
    assert reject_response.status_code == 400
    assert "Insufficient paper cash" in reject_response.json()["detail"]


def test_mvp_paper_trading_scheduler_status_route_returns_configuration():
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/scheduler")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["running"] is False
    assert payload["cron"] == "30 6 * * *"
    assert payload["timezone"] == "Asia/Shanghai"


def test_mvp_paper_trading_runs_route_returns_recent_runs(monkeypatch):
    run = PaperRunPayload(
        id="00000000-0000-0000-0000-000000000014",
        trading_day="2026-06-13",
        trigger="scheduled",
        status="completed",
        candidates_count=3,
        orders_count=1,
        positions_count=1,
        review_id="00000000-0000-0000-0000-000000000012",
        error_message=None,
        started_at="2026-06-13T00:00:00Z",
        finished_at="2026-06-13T00:01:00Z",
    )
    monkeypatch.setattr(mvp, "list_paper_runs", lambda session: [run], raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["trigger"] == "scheduled"
    assert payload["runs"][0]["status"] == "completed"
    assert payload["runs"][0]["orders_count"] == 1


def test_mvp_paper_trading_run_events_route_returns_core_events(monkeypatch):
    class EventPayload:
        def model_dump(self):
            return {
                "id": "00000000-0000-0000-0000-000000000015",
                "run_id": "00000000-0000-0000-0000-000000000014",
                "event_id": "core-order:1:new",
                "topic": "order_state",
                "sequence": 1,
                "correlation_id": "core-order",
                "causation_id": "core-intent",
                "payload_json": '{"state":"new"}',
                "published_at": "2026-06-13T00:00:00Z",
            }

    monkeypatch.setattr(mvp, "list_paper_run_events", lambda session, run_id: [EventPayload()], raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/runs/00000000-0000-0000-0000-000000000014/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"][0]["topic"] == "order_state"
    assert payload["events"][0]["payload_json"] == '{"state":"new"}'
