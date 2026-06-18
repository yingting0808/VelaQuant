from fastapi.testclient import TestClient
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlmodel import Session

from app.ai.schemas import ResearchResult, TradePlanDraft
from app.api.routes import mvp
from app.data.providers.base import ProviderStatus
from app.data.providers.openbb_optional import OpenBBOptionalProvider
from app.data.providers import registry
from app.data.providers.registry import HybridMarketDataProvider
from app.db.session import engine as db_engine
from app.domain.models import RuntimeConfiguration
from app.main import create_app
from app.services import strategy_catalog
from app.services.event_ledger import (
    EventLedgerReplay,
    EventLedgerReplayChain,
    EventLedgerStatus,
    EventLedgerTopicCount,
)
from app.services.alpha_validation import AlphaValidationPayload
from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload
from app.services.alpha_validation_snapshot import AlphaValidationSnapshotHistoryPayload, AlphaValidationSnapshotPayload
from app.services.alpha_validation_forecast import AlphaValidationForecastItem, AlphaValidationForecastPayload
from app.services.live_small_review import LiveSmallReviewPayload
from app.services.shadow_daily_report import ShadowDailyReportAction, ShadowDailyReportPayload
from app.services.shadow_review import ShadowReviewChecklistItem, ShadowReviewPayload, ShadowReviewResidualRisk
from app.services.shadow_observation import ShadowObservationPayload, ShadowObservationSummaryPayload
from app.services.shadow_observation_health import ShadowObservationHealthPayload
from app.services.shadow_validation import ShadowValidationPayload
from app.services.strategy_lifecycle_approval import (
    StrategyKillApprovalPayload,
    StrategyLiveSmallApprovalPayload,
    StrategyLifecycleReconcilePayload,
    StrategyShadowApprovalPayload,
)
from app.services.lean_backtest import BacktestHistoryItem, BacktestResult, BacktestStatistics
from app.services.paper_action_plan import PaperActionPlanItem, PaperActionPlanPayload
from app.services.paper_strategy_reviews import PaperStrategyReviewItem, PaperStrategyReviewsPayload
from app.services.paper_operations import (
    PaperOperationsHistoryItem,
    PaperOperationsHistoryPayload,
    PaperOperationsQuarantineItem,
    PaperOperationsQuarantinePayload,
    PaperOperationsRepairItem,
    PaperOperationsRepairPayload,
    PaperOperationsStatusPayload,
)
from app.services.paper_daily_report import PaperDailyReportPayload, PaperExitWatchItem
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, PaperExecutionRejectionReason
from app.services.paper_risk_profile import PaperRiskProfilePayload
from app.services.paper_risk_limit_review import PaperRiskLimitReviewPayload
from app.services.paper_risk_settings import PaperRiskLimitApplyPayload
from app.services.paper_review_trend import PaperReviewTrendItem, PaperReviewTrendPayload
from app.services.paper_scheduler import PaperSchedulerStatus
from app.services.paper_simulation import PaperSimulationPayload
from app.services.market_calendar import MarketSessionStatus
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
from app.services.strategy_lifecycle import StrategyLifecyclePayload, StrategyLifecycleRule
from app.services.strategy_lifecycle_audit import StrategyLifecycleAuditItem, StrategyLifecycleAuditPayload
from app.services.strategy_registry import StrategyRegistryEntry, StrategyRegistryPayload
from app.services.strategy_competition import (
    StrategyCompetitionEntryPayload,
    StrategyCompetitionPayload,
    StrategyCompetitionSnapshotPayload,
    StrategyCompetitionSnapshotHistoryPayload,
)
from app.services.strategy_runtime import StrategyCompetitionResult, StrategyRuntimeEntry
from app.services.strategy_versions import StrategyVersionControlPayload, StrategyVersionPayload
from app.services.execution_accounts import StrategyExecutionAccountPayload
from app.services.strategy_control import StrategyExecutionBinding, StrategyExecutionMode
from app.services.strategy_alpha_isolation import StrategyAlphaIsolationPayload
from app.services.trading_system_readiness import TradingSystemReadinessPayload
from app.trading_core.strategy import DeterministicWatchlistStrategy
from app.trading_core.strategy_engine import StrategyEngine
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


def _clear_runtime_settings() -> None:
    with Session(db_engine) as session:
        row = session.get(RuntimeConfiguration, "default")
        if row is not None:
            session.delete(row)
            session.commit()


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
    _clear_runtime_settings()

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
    _clear_runtime_settings()

    response = client.get("/api/mvp/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])


def test_mvp_runtime_settings_drive_data_provider_and_backtest_timeout(monkeypatch):
    observed: dict[str, float] = {}

    def fake_run(
        strategy_id: str,
        parameter_overrides: dict[str, str] | None = None,
        timeout_seconds: float = 0,
        market_data_provider: object | None = None,
    ) -> BacktestResult:
        observed["timeout_seconds"] = timeout_seconds
        return BacktestResult(
            run_id="20260612T101500Z-moving_average_cross",
            strategy_id=strategy_id,
            status="success",
            started_at="2026-06-12T10:15:00Z",
            completed_at="2026-06-12T10:16:15Z",
            duration_seconds=75.0,
            message="Backtest completed.",
            parameters=parameter_overrides or {},
            statistics=BacktestStatistics(total_net_profit="12.34%", sharpe_ratio="0.72"),
            equity=[],
            logs=[],
            output_directory="apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross",
        )

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app())
    _clear_runtime_settings()

    try:
        update_response = client.put(
            "/api/mvp/runtime-settings",
            json={
                "data_mode": "openbb_optional",
                "lean_backtest_timeout_seconds": 900,
                "openai_research_enabled": True,
                "openai_research_model": "gpt-5.5",
                "openai_base_url": "https://api.openai.com/v1",
                "openai_timeout_seconds": 20,
            },
        )
        data_response = client.get("/api/mvp/data-sources/status")
        backtest_response = client.post("/api/mvp/strategy-lab/backtests", json={"strategy_id": "moving_average_cross"})

        assert update_response.status_code == 200
        assert update_response.json()["data_mode"] == "openbb_optional"
        assert data_response.status_code == 200
        assert data_response.json()["provider_mode"] == "openbb_optional"
        assert backtest_response.status_code == 200
        assert observed["timeout_seconds"] == 900
    finally:
        _clear_runtime_settings()


def test_mvp_ai_status_route_reports_research_llm_isolated_from_execution(monkeypatch):
    monkeypatch.delenv("AI_STOCKS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/ai/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["langgraph"]["available"] is True
    assert payload["research_llm"]["provider"] == "openai_responses_or_chat_completions"
    assert payload["research_llm"]["available"] is False
    assert payload["execution_path"] == {
        "ai_generates_trade_intent": False,
        "ai_influences_risk": False,
        "ai_calls_execution": False,
    }


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
                    candidate_score_count=1,
                    average_candidate_score=1250,
                    latest_candidate_score=1250,
                    score_pnl_alignment="aligned",
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


def test_mvp_strategy_lab_alpha_isolation_route_returns_runtime_audit(monkeypatch):
    isolation = StrategyAlphaIsolationPayload(
        strategy_id="deterministic_watchlist_v1",
        isolated=True,
        strategy_order_count=12,
        manual_override_order_count=2,
        manual_override_event_chain_count=2,
        filtered_event_chain_count=12,
        summary="Manual override activity is isolated from alpha validation.",
    )
    monkeypatch.setattr(mvp, "get_strategy_alpha_isolation", lambda session: isolation, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/alpha-isolation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "deterministic_watchlist_v1"
    assert payload["isolated"] is True
    assert payload["manual_override_order_count"] == 2
    assert payload["filtered_event_chain_count"] == 12


def test_mvp_strategy_lab_lifecycle_route_returns_stage_gate(monkeypatch):
    lifecycle_payload = StrategyLifecyclePayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        current_stage="paper",
        recommended_stage="shadow_candidate",
        recommended_action="eligible_for_shadow_review",
        gate_status="eligible",
        promotion_gate="eligible_for_shadow",
        can_promote=True,
        can_kill=False,
        auto_actions_enabled=False,
        rules=[
            StrategyLifecycleRule(
                name="event_ledger_populated",
                passed=True,
                severity="blocker",
                actual="120 events",
                required="> 0 events",
                message="Event ledger is populated.",
            )
        ],
        missing_capabilities=["manual_promotion_approval"],
        summary="Eligible for manual review.",
    )

    monkeypatch.setattr(mvp, "get_strategy_lifecycle", lambda session: lifecycle_payload, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/lifecycle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_stage"] == "paper"
    assert payload["recommended_stage"] == "shadow_candidate"
    assert payload["recommended_action"] == "eligible_for_shadow_review"
    assert payload["can_promote"] is True
    assert payload["auto_actions_enabled"] is False
    assert payload["rules"][0]["name"] == "event_ledger_populated"


def test_mvp_strategy_lab_alpha_validation_route_returns_gate(monkeypatch):
    alpha_payload = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=False,
        validation_level="collecting",
        blockers=["consecutive_positive_expectancy"],
        has_real_market_backtest=True,
        review_day_count=3,
        consecutive_positive_expectancy_days=1,
        filled_order_count=12,
        closed_trade_count=4,
        event_chain_count=120,
        latest_expectancy=1.1,
        average_expectancy=0.6,
        max_drawdown=0.02,
        summary="fixture alpha validation",
    )

    monkeypatch.setattr(mvp, "get_alpha_validation", lambda session: alpha_payload, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/alpha-validation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["alpha_ready"] is False
    assert payload["blockers"] == ["consecutive_positive_expectancy"]
    assert payload["consecutive_positive_expectancy_days"] == 1


def test_mvp_strategy_lab_alpha_gates_route_returns_progress_payload(monkeypatch):
    progress = AlphaGateProgressPayload(
        alpha_ready=False,
        validation_level="collecting",
        passed_gates=2,
        total_gates=8,
        items=[
            AlphaGateProgressItem(
                gate="review_day_sample",
                label="复盘天数",
                current=3,
                required=5,
                remaining=2,
                unit="天",
                comparison="at_least",
                passed=False,
            )
        ],
        summary="Alpha gate progress: 2/8 gates passed.",
    )
    monkeypatch.setattr(mvp, "get_alpha_gate_progress", lambda session: progress, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/alpha-gates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed_gates"] == 2
    assert payload["items"][0]["remaining"] == 2


def test_mvp_strategy_lab_alpha_snapshots_route_returns_persisted_history(monkeypatch):
    snapshot = alpha_snapshot_payload(trading_day="2026-06-14")
    history = AlphaValidationSnapshotHistoryPayload(
        strategy_id="deterministic_watchlist_v1",
        snapshot_count=1,
        ready_snapshot_count=0,
        positive_expectancy_snapshot_count=1,
        positive_expectancy_streak=2,
        ready_streak=0,
        latest_blockers=["closed_trade_sample"],
        blocker_counts=[{"blocker": "closed_trade_sample", "count": 2}],
        latest=snapshot,
        items=[snapshot],
        summary="Alpha validation snapshots: 1 days recorded.",
    )
    monkeypatch.setattr(mvp, "get_alpha_validation_snapshots", lambda session: history, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/alpha-snapshots")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_count"] == 1
    assert payload["latest"]["trading_day"] == "2026-06-14"
    assert payload["positive_expectancy_snapshot_count"] == 1
    assert payload["positive_expectancy_streak"] == 2
    assert payload["latest_blockers"] == ["closed_trade_sample"]
    assert payload["blocker_counts"] == [{"blocker": "closed_trade_sample", "count": 2}]


def test_mvp_strategy_lab_alpha_snapshots_record_route_persists_current_snapshot(monkeypatch):
    snapshot = alpha_snapshot_payload(trading_day="2026-06-14")
    monkeypatch.setattr(mvp, "record_alpha_validation_snapshot", lambda session: snapshot, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/strategy-lab/alpha-snapshots/record")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trading_day"] == "2026-06-14"
    assert payload["latest_expectancy"] == 42.5


def test_mvp_strategy_lab_competition_route_returns_ranking_and_allocation(monkeypatch):
    competition = strategy_competition_payload()
    monkeypatch.setattr(mvp, "get_strategy_competition", lambda session, provider=None: competition, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/competition")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_count"] == 2
    assert payload["allocatable_strategy_count"] == 1
    assert payload["selected_strategy_id"] == "deterministic_watchlist_v1"
    assert payload["entries"][0]["allocation_weight"] == 1.0
    assert payload["entries"][1]["recommended_action"] == "keep_in_lab"


def test_mvp_strategy_lab_competition_snapshot_route_persists_daily_snapshot(monkeypatch):
    snapshot = StrategyCompetitionSnapshotPayload(
        **strategy_competition_payload().model_dump(),
        id=uuid4(),
        team_id=uuid4(),
        created_at="2026-06-14T00:00:00+00:00",
        updated_at="2026-06-14T00:00:00+00:00",
    )
    monkeypatch.setattr(mvp, "record_strategy_competition_snapshot", lambda session, provider=None: snapshot, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/strategy-lab/competition/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trading_day"] == "2026-06-14"
    assert payload["selected_strategy_id"] == "deterministic_watchlist_v1"
    assert payload["entries"][0]["eligible_for_allocation"] is True


def test_mvp_strategy_lab_competition_snapshots_route_returns_history(monkeypatch):
    snapshot = StrategyCompetitionSnapshotPayload(
        **strategy_competition_payload().model_dump(),
        id=uuid4(),
        team_id=uuid4(),
        created_at="2026-06-14T00:00:00+00:00",
        updated_at="2026-06-14T00:00:00+00:00",
    )
    history = StrategyCompetitionSnapshotHistoryPayload(
        snapshot_count=1,
        latest=snapshot,
        items=[snapshot],
        summary="Strategy competition snapshots: 1 days recorded, latest selected strategy deterministic_watchlist_v1.",
    )
    monkeypatch.setattr(mvp, "get_strategy_competition_snapshots", lambda session: history, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/competition/snapshots")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_count"] == 1
    assert payload["latest"]["selected_strategy_id"] == "deterministic_watchlist_v1"


def test_mvp_strategy_lab_alpha_forecast_route_returns_sessions_payload(monkeypatch):
    forecast = AlphaValidationForecastPayload(
        alpha_ready=False,
        status="forecastable",
        estimated_sessions_to_alpha_ready=5,
        limiting_gate="filled_order_sample",
        items=[
            AlphaValidationForecastItem(
                gate="filled_order_sample",
                label="成交订单",
                current=20,
                required=30,
                remaining=10,
                unit="笔",
                passed=False,
                estimated_per_session=2,
                estimated_sessions=5,
                reason="按当前样本速度估算。",
            )
        ],
        summary="Alpha validation needs about 5 more paper sessions.",
    )
    monkeypatch.setattr(mvp, "get_alpha_validation_forecast", lambda session: forecast, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/alpha-forecast")

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimated_sessions_to_alpha_ready"] == 5
    assert payload["limiting_gate"] == "filled_order_sample"


def test_mvp_strategy_lab_shadow_review_route_returns_review_packet(monkeypatch):
    packet = ShadowReviewPayload(
        status="ready_for_manual_review",
        strategy_id="deterministic_watchlist_v1",
        can_request_shadow_review=True,
        recommended_stage="shadow",
        auto_promotion_enabled=False,
        checklist=[
            ShadowReviewChecklistItem(
                code="alpha_gates_passed",
                label="Alpha 门禁通过",
                passed=True,
                evidence=["8/8"],
            )
        ],
        residual_risks=[
            ShadowReviewResidualRisk(
                code="paper_to_shadow_gap",
                severity="info",
                detail="模拟盘门禁通过只允许进入 Shadow 人工评审。",
                evidence=["auto_promotion_enabled=false"],
            )
        ],
        summary="Shadow review packet is ready for manual review; auto promotion is disabled.",
    )
    monkeypatch.setattr(mvp, "get_shadow_review_packet", lambda session: packet, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/shadow-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_for_manual_review"
    assert payload["auto_promotion_enabled"] is False
    assert payload["checklist"][0]["code"] == "alpha_gates_passed"


def test_mvp_strategy_lab_shadow_observations_route_returns_records(monkeypatch):
    observation = ShadowObservationPayload(
        id="00000000-0000-0000-0000-000000000201",
        team_id="00000000-0000-0000-0000-000000000202",
        strategy_id="deterministic_watchlist_v1",
        trading_day="2026-06-30",
        status="observing",
        can_request_shadow_review=True,
        observed_intent_count=6,
        would_route_order_count=6,
        event_chain_count=6,
        residual_risk_count=2,
        blocked_reason=None,
        created_at="2026-06-13T00:00:00Z",
    )
    summary = ShadowObservationSummaryPayload(
        can_record_shadow_observation=True,
        latest=observation,
        items=[observation],
        summary="Shadow observation latest observing on 2026-06-30.",
    )
    monkeypatch.setattr(mvp, "get_shadow_observations", lambda session: summary, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/shadow-observations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest"]["status"] == "observing"
    assert payload["latest"]["would_route_order_count"] == 6


def test_mvp_strategy_lab_record_shadow_observation_route_records_once(monkeypatch):
    observation = ShadowObservationPayload(
        id="00000000-0000-0000-0000-000000000201",
        team_id="00000000-0000-0000-0000-000000000202",
        strategy_id="deterministic_watchlist_v1",
        trading_day="2026-06-30",
        status="observing",
        can_request_shadow_review=True,
        observed_intent_count=6,
        would_route_order_count=6,
        event_chain_count=6,
        residual_risk_count=2,
        blocked_reason=None,
        created_at="2026-06-13T00:00:00Z",
    )
    monkeypatch.setattr(mvp, "record_shadow_observation", lambda session: observation, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/strategy-lab/shadow-observations/record")

    assert response.status_code == 200
    assert response.json()["trading_day"] == "2026-06-30"


def test_mvp_strategy_lab_record_shadow_observation_route_rejects_lifecycle_bypass(monkeypatch):
    def blocked_record(session):
        raise ValueError("Shadow observation requires current lifecycle stage shadow.")

    monkeypatch.setattr(mvp, "record_shadow_observation", blocked_record, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/strategy-lab/shadow-observations/record")

    assert response.status_code == 400
    assert "requires current lifecycle stage shadow" in response.json()["detail"]


def test_mvp_strategy_lab_approve_shadow_route_requires_manual_payload(monkeypatch):
    approval = StrategyShadowApprovalPayload(
        strategy_id="deterministic_watchlist_v1",
        previous_stage="paper",
        current_stage="shadow",
        approved_by="operator",
        reason="Reviewed.",
        auto_promotion_enabled=False,
        summary="Strategy manually approved for shadow.",
    )

    def fake_approval(session, request):
        assert request.approved_by == "operator"
        assert request.reason == "Reviewed."
        return approval

    monkeypatch.setattr(mvp, "approve_shadow_promotion", fake_approval, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/lifecycle/approve-shadow",
        json={"approved_by": "operator", "reason": "Reviewed."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_stage"] == "shadow"
    assert payload["auto_promotion_enabled"] is False


def test_mvp_strategy_lab_approve_live_small_route_requires_manual_payload(monkeypatch):
    approval = StrategyLiveSmallApprovalPayload(
        strategy_id="deterministic_watchlist_v1",
        previous_stage="shadow",
        current_stage="live_small",
        approved_by="operator",
        reason="Shadow sample reviewed.",
        auto_promotion_enabled=False,
        live_or_broker_execution_enabled=False,
        summary="Strategy manually approved for live-small review mode; broker execution remains disabled.",
    )

    def fake_approval(session, request):
        assert request.approved_by == "operator"
        assert request.reason == "Shadow sample reviewed."
        return approval

    monkeypatch.setattr(mvp, "approve_live_small_promotion", fake_approval, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/lifecycle/approve-live-small",
        json={"approved_by": "operator", "reason": "Shadow sample reviewed."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_stage"] == "live_small"
    assert payload["auto_promotion_enabled"] is False
    assert payload["live_or_broker_execution_enabled"] is False


def test_mvp_strategy_lab_approve_live_small_route_rejects_blocked_gate(monkeypatch):
    def blocked_approval(session, request):
        raise ValueError("Strategy deterministic_watchlist_v1 is not ready for live-small approval.")

    monkeypatch.setattr(mvp, "approve_live_small_promotion", blocked_approval, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/lifecycle/approve-live-small",
        json={"approved_by": "operator", "reason": "Too early."},
    )

    assert response.status_code == 400
    assert "not ready for live-small approval" in response.json()["detail"]


def test_mvp_strategy_lab_approve_kill_route_requires_manual_payload(monkeypatch):
    approval = StrategyKillApprovalPayload(
        strategy_id="deterministic_watchlist_v1",
        previous_stage="shadow",
        current_stage="killed",
        approved_by="operator",
        reason="Negative expectancy reviewed.",
        auto_promotion_enabled=False,
        execution_enabled=False,
        summary="Strategy manually killed; all execution remains disabled.",
    )

    def fake_approval(session, request):
        assert request.approved_by == "operator"
        assert request.reason == "Negative expectancy reviewed."
        return approval

    monkeypatch.setattr(mvp, "approve_strategy_kill", fake_approval, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/lifecycle/approve-kill",
        json={"approved_by": "operator", "reason": "Negative expectancy reviewed."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_stage"] == "killed"
    assert payload["execution_enabled"] is False


def test_mvp_strategy_lab_approve_kill_route_rejects_when_gate_is_not_ready(monkeypatch):
    def blocked_approval(session, request):
        raise ValueError("Strategy deterministic_watchlist_v1 is not ready for kill approval.")

    monkeypatch.setattr(mvp, "approve_strategy_kill", blocked_approval, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/lifecycle/approve-kill",
        json={"approved_by": "operator", "reason": "Too early."},
    )

    assert response.status_code == 400
    assert "not ready for kill approval" in response.json()["detail"]


def test_mvp_strategy_lab_lifecycle_reconcile_route_demotes_ahead_stage(monkeypatch):
    reconcile = StrategyLifecycleReconcilePayload(
        strategy_id="deterministic_watchlist_v1",
        previous_stage="shadow",
        current_stage="paper",
        reconciled=True,
        reconciled_by="system_reconcile",
        reason="Alpha validation is not ready.",
        alpha_ready=False,
        auto_promotion_enabled=False,
        execution_enabled=False,
        summary="Strategy deterministic_watchlist_v1 reconciled from shadow to paper.",
    )

    monkeypatch.setattr(mvp, "reconcile_lifecycle_with_alpha_validation", lambda session: reconcile, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/strategy-lab/lifecycle/reconcile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reconciled"] is True
    assert payload["previous_stage"] == "shadow"
    assert payload["current_stage"] == "paper"
    assert payload["alpha_ready"] is False
    assert payload["execution_enabled"] is False


def test_mvp_strategy_lab_shadow_validation_route_returns_gate_state(monkeypatch):
    validation = ShadowValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        shadow_ready=False,
        status="collecting",
        observation_count=1,
        observing_count=1,
        blocked_count=0,
        latest_trading_day="2026-06-30",
        min_observations_required=5,
        remaining_observations=4,
        residual_risk_count=2,
        blockers=["shadow_observation_sample"],
        summary="Shadow validation is collecting observations; 4 more observing samples required.",
    )
    monkeypatch.setattr(mvp, "get_shadow_validation", lambda session: validation, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/shadow-validation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["remaining_observations"] == 4


def test_mvp_strategy_lab_shadow_observation_health_route_returns_quality_state(monkeypatch):
    health = ShadowObservationHealthPayload(
        strategy_id="deterministic_watchlist_v1",
        status="collecting",
        sample_ready=False,
        observation_count=1,
        observing_count=1,
        blocked_count=0,
        consecutive_observing_count=1,
        latest_trading_day="2026-06-30",
        average_would_route_order_count=2,
        average_event_chain_count=6,
        average_residual_risk_count=2,
        warnings=["sample_not_ready"],
        summary="Shadow observation health is collecting samples; 1/5 observations recorded.",
    )
    monkeypatch.setattr(mvp, "get_shadow_observation_health", lambda session: health, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/shadow-observation-health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["warnings"] == ["sample_not_ready"]


def test_mvp_strategy_lab_shadow_daily_report_route_returns_next_action(monkeypatch):
    report = ShadowDailyReportPayload(
        strategy_id="deterministic_watchlist_v1",
        trading_day="2026-06-30",
        status="collecting",
        observation_status="observing",
        health_status="collecting",
        validation_status="collecting",
        live_small_status="blocked",
        observed_intent_count=6,
        would_route_order_count=2,
        event_chain_count=6,
        residual_risk_count=2,
        remaining_observations=4,
        warnings=["sample_not_ready"],
        blockers=["shadow_observation_sample"],
        next_actions=[
            ShadowDailyReportAction(
                priority=1,
                action_code="continue_shadow_observation",
                title="继续记录 Shadow 观察",
                detail="还需要 4 条 observing 样本，保持 broker 执行关闭。",
                evidence=["Shadow validation is collecting observations."],
            )
        ],
        live_or_broker_execution_enabled=False,
        summary="Shadow daily report is collecting observations; 4 more samples required.",
    )
    monkeypatch.setattr(mvp, "get_shadow_daily_report", lambda session: report, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/shadow-daily-report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting"
    assert payload["next_actions"][0]["action_code"] == "continue_shadow_observation"
    assert payload["live_or_broker_execution_enabled"] is False


def test_mvp_strategy_lab_live_small_review_route_returns_manual_gate(monkeypatch):
    review = LiveSmallReviewPayload(
        status="blocked",
        strategy_id="deterministic_watchlist_v1",
        can_request_live_small_review=False,
        recommended_stage="shadow",
        auto_promotion_enabled=False,
        checklist=[],
        residual_risks=[],
        summary="Live-small review packet is blocked; remain in Shadow or paper workflow until all gates pass.",
    )
    monkeypatch.setattr(mvp, "get_live_small_review_packet", lambda session: review, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/live-small-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["auto_promotion_enabled"] is False


def test_mvp_strategy_lab_lifecycle_audit_route_returns_entries(monkeypatch):
    audit = StrategyLifecycleAuditPayload(
        strategy_id="deterministic_watchlist_v1",
        items=[
            StrategyLifecycleAuditItem(
                id="00000000-0000-0000-0000-000000000301",
                action="strategy_shadow_approved",
                entity_type="strategy",
                entity_id="deterministic_watchlist_v1",
                approved_by="operator",
                reason="Paper gates reviewed.",
                previous_stage="paper",
                current_stage="shadow",
                auto_promotion_enabled=False,
                created_at="2026-06-13T00:00:00Z",
            )
        ],
        summary="1 lifecycle audit entries recorded for this strategy.",
    )
    monkeypatch.setattr(mvp, "get_strategy_lifecycle_audit", lambda session: audit, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/lifecycle/audit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["action"] == "strategy_shadow_approved"
    assert payload["items"][0]["current_stage"] == "shadow"


def test_mvp_strategy_lab_system_readiness_route_returns_operational_state(monkeypatch):
    readiness = TradingSystemReadinessPayload(
        status="operational",
        scheduler_running=True,
        scheduler_next_run_at="2026-06-14T06:30:00+08:00",
        lifecycle_stage="shadow",
        alpha_ready=True,
        event_bus_mode="redis",
        event_bus_ready=True,
        event_bus_stream_length=42,
        event_ledger_replay_ready=True,
        event_ledger_traceable_chain_count=8,
        event_ledger_complete_order_chain_count=8,
        event_ledger_broken_chain_count=0,
        event_ledger_traceability_ratio=1.0,
        shadow_can_record=True,
        shadow_remaining_observations=4,
        live_small_review_ready=False,
        live_or_broker_execution_enabled=False,
        manual_override_isolated=True,
        manual_override_order_count=2,
        manual_override_event_chain_count=2,
        alpha_filtered_event_chain_count=80,
        blockers=[],
        pending_gates=["shadow_validation_sample"],
        summary="Trading system is operational for controlled daily runs; pending gates: shadow_validation_sample.",
    )
    monkeypatch.setattr(mvp, "get_trading_system_readiness", lambda session: readiness, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/system-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "operational"
    assert payload["live_or_broker_execution_enabled"] is False


def test_mvp_strategy_lab_version_control_route_returns_active_binding(monkeypatch):
    version_payload = StrategyVersionControlPayload(
        active_strategy_id="deterministic_watchlist_v1",
        active_version="v2",
        previous_version="v1",
        versions=[
            StrategyVersionPayload(
                strategy_id="deterministic_watchlist_v1",
                version="v2",
                parameters_json='{"notional": 750}',
                status="registered",
                is_active=True,
            )
        ],
    )

    monkeypatch.setattr(mvp, "get_strategy_version_control", lambda session: version_payload, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/version-control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_version"] == "v2"
    assert payload["versions"][0]["is_active"] is True


def test_mvp_strategy_lab_version_control_routes_mutate_binding(monkeypatch):
    calls = []
    payload = StrategyVersionControlPayload(
        active_strategy_id="deterministic_watchlist_v1",
        active_version="v2",
        previous_version="v1",
        versions=[],
    )

    def fake_register(session, *, strategy_id, version, parameters_json):
        calls.append(("register", strategy_id, version, parameters_json))
        return StrategyVersionPayload(
            strategy_id=strategy_id,
            version=version,
            parameters_json=parameters_json,
            status="registered",
            is_active=False,
        )

    def fake_activate(session, *, strategy_id, version, reason):
        calls.append(("activate", strategy_id, version, reason))
        return payload

    def fake_rollback(session, *, strategy_id):
        calls.append(("rollback", strategy_id))
        return payload

    monkeypatch.setattr(mvp, "register_strategy_version", fake_register, raising=False)
    monkeypatch.setattr(mvp, "activate_strategy_version", fake_activate, raising=False)
    monkeypatch.setattr(mvp, "rollback_strategy_version", fake_rollback, raising=False)
    client = TestClient(create_app())

    register_response = client.post(
        "/api/mvp/strategy-lab/version-control/versions",
        json={
            "strategy_id": "deterministic_watchlist_v1",
            "version": "v2",
            "parameters_json": '{"notional": 750}',
        },
    )
    activate_response = client.post(
        "/api/mvp/strategy-lab/version-control/activate",
        json={"strategy_id": "deterministic_watchlist_v1", "version": "v2", "reason": "test"},
    )
    rollback_response = client.post(
        "/api/mvp/strategy-lab/version-control/rollback",
        json={"strategy_id": "deterministic_watchlist_v1"},
    )

    assert register_response.status_code == 200
    assert activate_response.status_code == 200
    assert rollback_response.status_code == 200
    assert calls == [
        ("register", "deterministic_watchlist_v1", "v2", '{"notional": 750}'),
        ("activate", "deterministic_watchlist_v1", "v2", "test"),
        ("rollback", "deterministic_watchlist_v1"),
    ]


def test_mvp_strategy_lab_runtime_route_returns_competition(monkeypatch):
    runtime_payload = StrategyCompetitionResult(
        winner=StrategyRuntimeEntry(
            strategy_id="deterministic_watchlist_v1",
            version="v2",
            ranking_score=72,
            eligible=True,
            rank=1,
        ),
        entries=[
            StrategyRuntimeEntry(
                strategy_id="deterministic_watchlist_v1",
                version="v2",
                ranking_score=72,
                eligible=True,
                rank=1,
            )
        ],
        summary="fixture",
    )

    monkeypatch.setattr(mvp, "get_strategy_runtime_status", lambda session: runtime_payload, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["winner"]["version"] == "v2"
    assert payload["entries"][0]["rank"] == 1


def test_mvp_strategy_lab_execution_accounts_route_returns_modes(monkeypatch):
    account_payload = [
        StrategyExecutionAccountPayload(
            id="00000000-0000-0000-0000-000000000001",
            team_id="00000000-0000-0000-0000-000000000002",
            strategy_id="deterministic_watchlist_v1",
            name="paper",
            mode="paper",
            starting_cash=100000,
            cash=100000,
            realized_pnl=0,
        ),
        StrategyExecutionAccountPayload(
            id="00000000-0000-0000-0000-000000000003",
            team_id="00000000-0000-0000-0000-000000000002",
            strategy_id="deterministic_watchlist_v1",
            name="live-small",
            mode="live_small",
            starting_cash=5000,
            cash=5000,
            realized_pnl=0,
        ),
    ]

    monkeypatch.setattr(
        mvp,
        "get_workspace_summary",
        lambda session: WorkspaceSummary(
            team_id="00000000-0000-0000-0000-000000000002",
            team_name="fixture",
            portfolio_id="00000000-0000-0000-0000-000000000004",
            portfolio_name="fixture",
            position_count=0,
            watchlist_count=0,
            note_count=0,
        ),
        raising=False,
    )
    monkeypatch.setattr(mvp, "get_or_create_strategy_execution_accounts", lambda session, *, team_id, strategy_id: account_payload, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/execution-accounts")

    assert response.status_code == 200
    assert [item["mode"] for item in response.json()["accounts"]] == ["paper", "live_small"]


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


def test_mvp_research_route_injects_optional_llm_client(monkeypatch):
    llm_client = object()
    captured = {}

    def fake_run_research_workflow(request, llm_client=None):
        captured["ticker"] = request.ticker
        captured["llm_client"] = llm_client
        return ResearchResult(
            ticker="AAPL",
            status="complete_llm",
            summary="LLM summary.",
            bull_case="Bull.",
            bear_case="Bear.",
            watch_items=["Watch."],
            evidence_count=len(request.evidence),
            trade_plan_draft=TradePlanDraft(
                entry_condition="Human review confirms the thesis.",
                invalidation_condition="Evidence turns negative.",
                risk_notes=["Research only."],
            ),
        )

    monkeypatch.setattr(mvp, "build_openai_research_client", lambda settings: llm_client, raising=False)
    monkeypatch.setattr(mvp, "run_research_workflow", fake_run_research_workflow, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/research",
        json={"ticker": "AAPL", "question": "What changed?"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "complete_llm"
    assert captured == {"ticker": "AAPL", "llm_client": llm_client}


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
        "risk_decision",
        "order_state",
    ]
    assert payload["events"][-1]["payload"]["current_state"] == "filled"


def test_trading_core_dry_run_uses_active_version_notional_when_request_omits_override(monkeypatch):
    captured = {}

    def fake_binding(session, team_id, strategy_id, *, notional=None):
        captured["notional"] = notional
        strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=750)
        return StrategyExecutionBinding(
            strategy_id="deterministic_watchlist_v1",
            name="Deterministic Watchlist Strategy",
            version="v2",
            execution_mode=StrategyExecutionMode.paper,
            strategy_engine=StrategyEngine(strategy_id="deterministic_watchlist_v1", strategy=strategy),
            supports_live=False,
            supports_hot_swap=True,
        )

    monkeypatch.setattr(mvp, "get_strategy_execution_binding", fake_binding, raising=False)
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
            "risk_limits": {"max_order_notional": 5000},
        },
    )

    assert response.status_code == 200
    assert captured["notional"] is None
    assert response.json()["intents"][0]["notional"] == 750


def test_trading_core_dry_run_returns_400_when_strategy_control_blocks(monkeypatch):
    def blocked_execution(session, strategy_id, *, requested_mode):
        raise ValueError("Lifecycle marks strategy deterministic_watchlist_v1 for kill review; execution is blocked.")

    monkeypatch.setattr(mvp, "assert_strategy_execution_allowed", blocked_execution, raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)

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
            "risk_limits": {"max_order_notional": 5000},
        },
    )

    assert response.status_code == 400
    assert "kill review" in response.json()["detail"]


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

    def fake_run(
        strategy_id: str,
        parameter_overrides: dict[str, str] | None = None,
        timeout_seconds: float = 0,
        market_data_provider: object | None = None,
    ) -> BacktestResult:
        assert strategy_id == "moving_average_cross"
        assert parameter_overrides == {"symbol": "MSFT", "fast_period": "10", "slow_period": "30"}
        assert timeout_seconds == 600.0
        return result

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app())
    _clear_runtime_settings()

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


def test_mvp_strategy_lab_candidate_backtest_route_returns_ranked_candidates(monkeypatch):
    class CandidateBacktestPayload:
        def model_dump(self):
            return {
                "strategy_id": "deterministic_watchlist_v1",
                "candidate_count": 2,
                "real_market_candidate_count": 2,
                "best_ticker": "NVDA",
                "items": [
                    {
                        "rank": 1,
                        "ticker": "NVDA",
                        "recommendation": "candidate",
                        "score": 1.42,
                        "reason": "真实历史数据；收益为正。",
                    }
                ],
                "summary": "Ranked 2 candidates.",
            }

    def fake_candidate_run(
        *,
        strategy_id: str,
        tickers: list[str],
        parameter_overrides: dict[str, str] | None = None,
        market_data_provider=None,
    ) -> CandidateBacktestPayload:
        assert strategy_id == "deterministic_watchlist_v1"
        assert tickers == ["aapl", "nvda"]
        assert parameter_overrides == {"start_date": "2020-01-01", "end_date": "2021-01-01"}
        assert market_data_provider is not None
        return CandidateBacktestPayload()

    monkeypatch.setattr(mvp, "run_strategy_candidate_backtests", fake_candidate_run, raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/candidate-backtests",
        json={
            "strategy_id": "deterministic_watchlist_v1",
            "tickers": ["aapl", "nvda"],
            "parameters": {"start_date": "2020-01-01", "end_date": "2021-01-01"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["best_ticker"] == "NVDA"
    assert payload["items"][0]["recommendation"] == "candidate"


def test_mvp_strategy_lab_backtest_route_rejects_unknown_strategy(monkeypatch):
    def fake_run(
        strategy_id: str,
        parameter_overrides: dict[str, str] | None = None,
        timeout_seconds: float = 0,
        market_data_provider: object | None = None,
    ) -> BacktestResult:
        raise strategy_catalog.UnknownStrategyError("Unknown strategy_id: missing")

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "missing"},
    )

    assert response.status_code == 404


def test_mvp_strategy_lab_backtest_route_rejects_invalid_parameters(monkeypatch):
    def fake_run(
        strategy_id: str,
        parameter_overrides: dict[str, str] | None = None,
        timeout_seconds: float = 0,
        market_data_provider: object | None = None,
    ) -> BacktestResult:
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
    def fake_run(
        strategy_id: str,
        parameter_overrides: dict[str, str] | None = None,
        timeout_seconds: float = 0,
    ) -> BacktestResult:
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
    call_args = {}

    def fake_summary(session, provider, *, use_live_quotes=True):
        call_args["use_live_quotes"] = use_live_quotes
        return _paper_trading_summary_payload()

    monkeypatch.setattr(mvp, "get_paper_trading_summary", fake_summary, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"]["name"] == "默认模拟盘"
    assert payload["account"]["mode"] == "paper"
    assert payload["candidates"][0]["ticker"] == "NVDA"
    assert payload["latest_review"]["readiness"] == "collecting"
    assert call_args["use_live_quotes"] is False


def test_mvp_paper_trading_summary_route_can_refresh_quotes(monkeypatch):
    call_args = {}

    def fake_summary(session, provider, *, use_live_quotes=True):
        call_args["use_live_quotes"] = use_live_quotes
        return _paper_trading_summary_payload()

    monkeypatch.setattr(mvp, "get_paper_trading_summary", fake_summary, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/summary?refresh_quotes=true")

    assert response.status_code == 200
    assert call_args["use_live_quotes"] is True


def test_mvp_paper_trading_daily_run_route_generates_candidates(monkeypatch):
    monkeypatch.setattr(mvp, "run_daily_paper_trading_loop", lambda session, provider: _paper_trading_summary_payload(), raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/daily-run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"][0]["action"] == "buy"
    assert "证据" in payload["candidates"][0]["thesis"]


def test_mvp_paper_trading_daily_run_route_returns_400_when_run_lock_is_active(monkeypatch):
    def locked_daily_run(session, provider):
        raise ValueError("Paper trading run is already running for 2026-06-13.")

    monkeypatch.setattr(mvp, "run_daily_paper_trading_loop", locked_daily_run, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/daily-run")

    assert response.status_code == 400
    assert "already running for 2026-06-13" in response.json()["detail"]


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


def test_mvp_paper_trading_order_route_rejects_unknown_strategy(monkeypatch):
    def fake_submit(session, provider, data: PaperOrderCreate) -> PaperOrderPayload:
        raise AssertionError("route should reject the strategy before submitting the paper order")

    monkeypatch.setattr(mvp, "submit_paper_order", fake_submit, raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/paper-trading/orders",
        json={
            "ticker": "nvda",
            "side": "buy",
            "quantity": 10,
            "order_type": "market",
            "strategy_id": "missing_strategy",
        },
    )

    assert response.status_code == 400
    assert "Strategy is not registered for execution" in response.json()["detail"]


def test_mvp_paper_trading_scheduler_status_route_returns_configuration(monkeypatch):
    status = PaperSchedulerStatus(
        enabled=False,
        running=False,
        job_count=0,
        job_id="paper_trading_daily_run",
        cron="30 6 * * *",
        timezone="Asia/Shanghai",
        next_run_at=None,
        last_checked_at=datetime(2026, 6, 14, 13, 0, tzinfo=timezone.utc),
        can_run_now=False,
        execution_gate="market_closed",
        market_date="2026-06-14",
        trading_day="2026-06-12",
        is_market_session=False,
        session_closed=False,
        calendar_provider="test",
        gate_reason="market_closed",
    )
    monkeypatch.setattr(mvp, "get_paper_scheduler_status", lambda: status, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/scheduler")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["running"] is False
    assert payload["cron"] == "30 6 * * *"
    assert payload["timezone"] == "Asia/Shanghai"
    assert payload["job_id"] == "paper_trading_daily_run"
    assert payload["next_run_at"] is None
    assert payload["last_checked_at"] is not None


def test_mvp_paper_trading_operations_route_returns_health(monkeypatch):
    status = PaperOperationsStatusPayload(
        trading_day="2026-06-13",
        run_state="completed",
        health_status="ready",
        latest_run_id="00000000-0000-0000-0000-000000000014",
        latest_run_trading_day="2026-06-13",
        latest_run_status="completed",
        today_run_id="00000000-0000-0000-0000-000000000014",
        review_id="00000000-0000-0000-0000-000000000012",
        latest_error=None,
        can_retry_today=False,
        event_ledger_ready=True,
        latest_run_event_count=8,
        legacy_manual_future_run_count=0,
        latest_legacy_manual_future_trading_day=None,
        data_quality_warnings=[],
        blockers=[],
        recommended_action="hold_until_next_session",
        summary="Daily paper pipeline is complete.",
    )
    monkeypatch.setattr(mvp, "get_paper_operations_status", lambda session: status, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/operations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_state"] == "completed"
    assert payload["health_status"] == "ready"
    assert payload["event_ledger_ready"] is True
    assert payload["recommended_action"] == "hold_until_next_session"


def test_mvp_paper_trading_operations_history_route_returns_trend(monkeypatch):
    history = PaperOperationsHistoryPayload(
        window_size=2,
        completed_days=1,
        failed_days=1,
        blocked_days=1,
        replayable_days=1,
        review_days=1,
        completion_rate=0.5,
        replay_rate=0.5,
        latest_health_status="blocked",
        items=[
            PaperOperationsHistoryItem(
                trading_day="2026-06-13",
                run_id="00000000-0000-0000-0000-000000000014",
                status="failed",
                health_status="blocked",
                event_count=0,
                has_review=False,
                candidates_count=0,
                orders_count=0,
                positions_count=0,
                blockers=["latest_run_failed"],
                error_message="provider timeout",
                started_at="2026-06-13T00:00:00Z",
                finished_at="2026-06-13T00:01:00Z",
            ),
            PaperOperationsHistoryItem(
                trading_day="2026-06-12",
                run_id="00000000-0000-0000-0000-000000000015",
                status="completed",
                health_status="ready",
                event_count=8,
                has_review=True,
                candidates_count=3,
                orders_count=1,
                positions_count=1,
                blockers=[],
                error_message=None,
                started_at="2026-06-12T00:00:00Z",
                finished_at="2026-06-12T00:01:00Z",
            ),
        ],
        summary="Last 2 paper runs include 1 blocked and 1 failed runs.",
    )
    monkeypatch.setattr(mvp, "get_paper_operations_history", lambda session: history, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/operations/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_size"] == 2
    assert payload["completion_rate"] == 0.5
    assert payload["replay_rate"] == 0.5
    assert payload["latest_health_status"] == "blocked"
    assert payload["items"][0]["blockers"] == ["latest_run_failed"]


def test_mvp_paper_trading_repair_event_ledger_route_returns_repair_summary(monkeypatch):
    repair = PaperOperationsRepairPayload(
        scanned_runs=2,
        repaired_runs=1,
        skipped_runs=1,
        items=[
            PaperOperationsRepairItem(
                run_id="00000000-0000-0000-0000-000000000014",
                trading_day="2026-06-13",
                status="skipped",
                event_created=True,
                topic="run_audit",
                reason="audit_event_created",
            ),
            PaperOperationsRepairItem(
                run_id="00000000-0000-0000-0000-000000000015",
                trading_day="2026-06-12",
                status="failed",
                event_created=False,
                topic=None,
                reason="status_not_repairable",
            ),
        ],
        summary="Scanned 2 paper runs; repaired 1 missing event ledgers and skipped 1.",
    )
    monkeypatch.setattr(mvp, "repair_paper_operations_event_ledger", lambda session: repair, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/operations/repair-ledger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scanned_runs"] == 2
    assert payload["repaired_runs"] == 1
    assert payload["items"][0]["topic"] == "run_audit"


def test_mvp_paper_trading_quarantine_legacy_runs_route_returns_summary(monkeypatch):
    quarantine = PaperOperationsQuarantinePayload(
        scanned_runs=1,
        quarantined_runs=1,
        skipped_runs=0,
        items=[
            PaperOperationsQuarantineItem(
                run_id="00000000-0000-0000-0000-000000000015",
                trading_day="2026-06-30",
                status="completed",
                previous_trigger="manual",
                new_trigger="simulation",
                audit_event_created=True,
                reason="manual_future_dated_run_reclassified_as_simulation",
            )
        ],
        summary="Scanned 1 legacy manual future-dated runs; quarantined 1 as simulation and skipped 0.",
    )
    monkeypatch.setattr(mvp, "quarantine_legacy_manual_future_runs", lambda session: quarantine, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/operations/quarantine-legacy-runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scanned_runs"] == 1
    assert payload["quarantined_runs"] == 1
    assert payload["items"][0]["new_trigger"] == "simulation"


def test_mvp_paper_trading_review_trend_route_returns_expectancy_window(monkeypatch):
    trend = PaperReviewTrendPayload(
        sample_size=2,
        positive_expectancy_days=2,
        consecutive_positive_expectancy_days=2,
        average_expectancy=1.1,
        latest_expectancy=1.2,
        total_realized_pnl=20,
        total_unrealized_pnl=40,
        latest_readiness="watch",
        items=[
                PaperReviewTrendItem(
                    trading_day="2026-06-13",
                    equity=100300,
                    daily_pnl=300,
                    daily_return=0.003,
                    cash=95000,
                    realized_pnl=10,
                unrealized_pnl=20,
                trade_count=1,
                win_rate=0.5,
                expectancy=1.2,
                readiness="watch",
            )
        ],
        summary="Paper review trend is positive.",
    )
    monkeypatch.setattr(mvp, "get_paper_review_trend", lambda session: trend, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/review-trend")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_size"] == 2
    assert payload["latest_expectancy"] == 1.2
    assert payload["items"][0]["trading_day"] == "2026-06-13"


def test_mvp_paper_trading_daily_report_route_returns_operational_summary(monkeypatch):
    report = PaperDailyReportPayload(
        trading_day="2026-06-13",
        run_state="completed",
        health_status="ready",
        recommended_action="hold_until_next_session",
        scheduler_running=True,
        scheduler_next_run_at="2026-06-14T06:30:00+08:00",
        scheduler_next_run_will_execute=False,
        scheduler_next_run_execution_gate="market_closed",
        scheduler_next_actionable_run_at="2026-06-15T06:30:00+08:00",
        scheduler_next_actionable_trading_day="2026-06-14",
        scheduler_next_actionable_execution_gate="ready_to_run",
        estimated_sessions_to_alpha_ready=4,
        limiting_alpha_gate="review_day_sample",
        account_equity=100000,
        cash=98000,
        realized_pnl=0,
        unrealized_pnl=0,
        daily_pnl=125.5,
        daily_return=0.0013,
        candidate_count=3,
        actionable_candidate_count=2,
        ordered_candidate_count=1,
        dismissed_candidate_count=0,
        order_count=1,
        open_position_count=1,
        latest_expectancy=0,
        average_expectancy=0,
        consecutive_positive_expectancy_days=0,
        event_ledger_ready=True,
        alpha_ready=False,
        alpha_blockers=["review_day_sample"],
        open_alpha_gates=[
            AlphaGateProgressItem(
                gate="filled_order_sample",
                label="成交订单",
                current=10,
                required=30,
                remaining=20,
                unit="笔",
                comparison="at_least",
                passed=False,
            )
        ],
        exit_watchlist=[
            PaperExitWatchItem(
                ticker="AAPL",
                quantity=2,
                return_pct=0.15,
                unrealized_pnl=30,
                trigger="take_profit",
                triggered=True,
                threshold_pct=0.1,
                distance_to_trigger_pct=0,
                next_exit_quantity=2,
            )
        ],
        data_quality_warnings=[],
        summary="Daily paper report.",
    )
    monkeypatch.setattr(mvp, "get_paper_daily_report", lambda session, provider: report, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/daily-report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["health_status"] == "ready"
    assert payload["candidate_count"] == 3
    assert payload["actionable_candidate_count"] == 2
    assert payload["ordered_candidate_count"] == 1
    assert payload["dismissed_candidate_count"] == 0
    assert payload["event_ledger_ready"] is True
    assert payload["daily_pnl"] == 125.5
    assert payload["daily_return"] == 0.0013
    assert payload["alpha_blockers"] == ["review_day_sample"]
    assert payload["open_alpha_gates"][0]["gate"] == "filled_order_sample"
    assert payload["open_alpha_gates"][0]["remaining"] == 20
    assert payload["exit_watchlist"][0]["ticker"] == "AAPL"
    assert payload["exit_watchlist"][0]["trigger"] == "take_profit"
    assert payload["scheduler_next_run_will_execute"] is False
    assert payload["scheduler_next_actionable_trading_day"] == "2026-06-14"
    assert payload["estimated_sessions_to_alpha_ready"] == 4
    assert payload["limiting_alpha_gate"] == "review_day_sample"


def test_mvp_paper_simulation_route_runs_lab_window(monkeypatch):
    simulation = PaperSimulationPayload(
        scenario="bullish",
        start_date="2026-06-14",
        days_requested=2,
        days_completed=2,
        days_skipped=0,
        review_day_count=2,
        consecutive_positive_expectancy_days=0,
        latest_expectancy=0,
        average_expectancy=0,
        event_chain_count=2,
        alpha_ready=False,
        blockers=["closed_trade_sample"],
        items=[],
        summary="Paper simulation fixture.",
    )
    monkeypatch.setattr(mvp, "run_paper_simulation_lab", lambda session, provider, request: simulation, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/simulation/run", json={"days": 2, "scenario": "bullish"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["days_completed"] == 2
    assert payload["blockers"] == ["closed_trade_sample"]


def test_mvp_paper_execution_diagnostics_route_returns_order_quality(monkeypatch):
    diagnostics = PaperExecutionDiagnosticsPayload(
        order_count=4,
        filled_order_count=2,
        rejected_order_count=2,
        buy_order_count=2,
        sell_order_count=2,
        closed_trade_count=1,
        fill_rate=0.5,
        rejection_rate=0.5,
        realized_pnl=120,
        average_realized_pnl=120,
        latest_rejection_code="max_daily_orders",
        max_daily_order_rejections=1,
        max_daily_order_buy_rejections=1,
        max_daily_order_sell_rejections=0,
        rejection_reasons=[
            PaperExecutionRejectionReason(
                risk_code="max_daily_orders",
                count=1,
                latest_reason="Orders today 5 reached limit 5.",
            )
        ],
        summary="Paper execution diagnostics.",
    )
    monkeypatch.setattr(mvp, "get_paper_execution_diagnostics", lambda session: diagnostics, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/execution-diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filled_order_count"] == 2
    assert payload["max_daily_order_buy_rejections"] == 1
    assert payload["max_daily_order_sell_rejections"] == 0
    assert payload["rejection_reasons"][0]["risk_code"] == "max_daily_orders"


def test_mvp_paper_risk_profile_route_returns_limits(monkeypatch):
    profile = PaperRiskProfilePayload(
        risk_engine="Trading Core RiskEngine",
        max_order_notional=2000,
        max_position_weight=0.1,
        max_daily_orders=5,
        exit_take_profit_pct=0.1,
        exit_stop_loss_pct=-0.05,
        summary="Paper risk profile.",
    )
    monkeypatch.setattr(mvp, "get_paper_risk_profile", lambda session: profile, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/risk-profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["max_daily_orders"] == 5
    assert payload["exit_take_profit_pct"] == 0.1


def test_mvp_paper_risk_limit_review_route_returns_paper_only_recommendation(monkeypatch):
    review = PaperRiskLimitReviewPayload(
        status="review_required",
        current_max_daily_orders=5,
        recommended_paper_max_daily_orders=6,
        live_change_allowed=False,
        max_daily_order_rejections=26,
        max_daily_order_buy_rejections=6,
        max_daily_order_sell_rejections=20,
        filled_order_count=42,
        closed_trade_count=20,
        sample_collection_blocked=True,
        blockers=["filled_order_sample", "closed_trade_sample", "max_daily_orders"],
        summary="Paper risk limit review: paper-only review required.",
    )
    monkeypatch.setattr(mvp, "get_paper_risk_limit_review", lambda session: review, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/risk-limit-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "review_required"
    assert payload["recommended_paper_max_daily_orders"] == 6
    assert payload["max_daily_order_buy_rejections"] == 6
    assert payload["max_daily_order_sell_rejections"] == 20
    assert payload["live_change_allowed"] is False


def test_mvp_apply_paper_risk_limit_recommendation_route_returns_paper_only_result(monkeypatch):
    result = PaperRiskLimitApplyPayload(
        applied=True,
        previous_max_daily_orders=5,
        applied_max_daily_orders=6,
        live_change_allowed=False,
        audit_event_created=True,
        summary="Paper risk limit recommendation applied: max_daily_orders 5 -> 6; live limits unchanged.",
    )
    monkeypatch.setattr(mvp, "apply_paper_risk_limit_recommendation", lambda session: result, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/risk-limit-review/apply-paper-recommendation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is True
    assert payload["previous_max_daily_orders"] == 5
    assert payload["applied_max_daily_orders"] == 6
    assert payload["live_change_allowed"] is False
    assert payload["audit_event_created"] is True


def test_mvp_paper_action_plan_route_returns_prioritized_actions(monkeypatch):
    plan = PaperActionPlanPayload(
        readiness="ready",
        primary_action="review_daily_order_limit",
        items=[
            PaperActionPlanItem(
                priority=2,
                action_code="review_daily_order_limit",
                title="复核日订单上限",
                detail="max_daily_orders=5",
                evidence=["rejected=26"],
            )
        ],
        summary="Paper action plan primary action: review_daily_order_limit.",
    )
    monkeypatch.setattr(mvp, "get_paper_action_plan", lambda session: plan, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/action-plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_action"] == "review_daily_order_limit"
    assert payload["items"][0]["action_code"] == "review_daily_order_limit"


def test_mvp_paper_action_plan_execute_primary_route_runs_safe_default_action(monkeypatch):
    plan = PaperActionPlanPayload(
        readiness="ready",
        primary_action="apply_paper_risk_limit_recommendation",
        items=[
            PaperActionPlanItem(
                priority=2,
                action_code="apply_paper_risk_limit_recommendation",
                title="应用 Paper 限额建议",
                detail="按默认推荐提高模拟盘样本采集容量。",
                evidence=["rejected=26"],
            )
        ],
        summary="Paper action plan primary action: apply_paper_risk_limit_recommendation.",
    )

    class ExecutePayload:
        def model_dump(self):
            return {
                "executed": True,
                "queued": False,
                "status": "completed",
                "action_code": "apply_paper_risk_limit_recommendation",
                "next_primary_action": "collect_post_limit_sample",
                "result": None,
                "summary": "Executed primary action apply_paper_risk_limit_recommendation; next action collect_post_limit_sample.",
            }

    monkeypatch.setattr(mvp, "get_paper_action_plan", lambda session: plan, raising=False)
    monkeypatch.setattr(mvp, "execute_paper_primary_action", lambda session, provider: ExecutePayload(), raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/action-plan/execute-primary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed"] is True
    assert payload["action_code"] == "apply_paper_risk_limit_recommendation"
    assert payload["next_primary_action"] == "collect_post_limit_sample"


def test_mvp_paper_action_plan_execute_primary_route_queues_long_paper_action(monkeypatch):
    plan = PaperActionPlanPayload(
        readiness="ready",
        primary_action="collect_post_limit_sample",
        items=[
            PaperActionPlanItem(
                priority=2,
                action_code="collect_post_limit_sample",
                title="收集新限额样本",
                detail="等待下一次真实 paper 运行后判断新限额。",
                evidence=["filled=42"],
            )
        ],
        summary="Paper action plan primary action: collect_post_limit_sample.",
    )
    calls = []

    class QueuePayload:
        def model_dump(self):
            return {
                "executed": False,
                "queued": True,
                "status": "queued",
                "action_code": "collect_post_limit_sample",
                "next_primary_action": "collect_post_limit_sample",
                "result": {"status_url": "/api/mvp/paper-trading/runs"},
                "summary": "Queued primary action collect_post_limit_sample.",
            }

    def queue_action(session, background_tasks):
        calls.append(background_tasks)
        return QueuePayload()

    def execute_action(session, provider):
        raise AssertionError("long paper action should be queued")

    monkeypatch.setattr(mvp, "get_paper_action_plan", lambda session: plan, raising=False)
    monkeypatch.setattr(mvp, "queue_paper_primary_action", queue_action, raising=False)
    monkeypatch.setattr(mvp, "execute_paper_primary_action", execute_action, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/action-plan/execute-primary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] is True
    assert payload["status"] == "queued"
    assert payload["action_code"] == "collect_post_limit_sample"
    assert len(calls) == 1


def test_mvp_paper_strategy_reviews_route_returns_runtime_review_records(monkeypatch):
    reviews = PaperStrategyReviewsPayload(
        review_count=1,
        items=[
            PaperStrategyReviewItem(
                event_id="paper_action:review_score_pnl_inversion:AAPL,NVDA:2:strategy_review",
                action_code="review_score_pnl_inversion",
                title="复盘评分背离",
                detail="AAPL/NVDA 评分与盈亏反向。",
                evidence=["inverted_tickers=AAPL,NVDA", "score_pnl_inversion_count=2"],
                inverted_tickers=["AAPL", "NVDA"],
                review_status="required",
                created_at=datetime(2026, 6, 15, 1, 2, 3, tzinfo=timezone.utc),
            )
        ],
        summary="Strategy reviews: 1 recorded; latest review_score_pnl_inversion covers AAPL,NVDA.",
    )
    monkeypatch.setattr(mvp, "get_paper_strategy_reviews", lambda session: reviews, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/strategy-reviews")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_count"] == 1
    assert payload["items"][0]["action_code"] == "review_score_pnl_inversion"
    assert payload["items"][0]["inverted_tickers"] == ["AAPL", "NVDA"]


def test_mvp_paper_market_session_route_explains_effective_trading_day(monkeypatch):
    status = MarketSessionStatus(
        market_date="2026-06-13",
        trading_day="2026-06-12",
        is_market_session=False,
        session_closed=False,
        calendar_provider="pandas_market_calendars",
        reason="market_closed",
    )
    monkeypatch.setattr(mvp, "get_market_session_status", lambda: status, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/market-session")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "market_date": "2026-06-13",
        "trading_day": "2026-06-12",
        "is_market_session": False,
        "session_closed": False,
        "calendar_provider": "pandas_market_calendars",
        "reason": "market_closed",
    }


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


def test_mvp_paper_trading_event_ledger_route_returns_replay_status(monkeypatch):
    status = EventLedgerStatus(
        total_event_count=8,
        latest_run_id="00000000-0000-0000-0000-000000000014",
        latest_run_status="completed",
        latest_run_event_count=8,
        latest_topic_counts=[
            EventLedgerTopicCount(topic="market_event", count=1),
            EventLedgerTopicCount(topic="order_state", count=5),
        ],
        latest_correlation_count=1,
        replay_ready=True,
        warnings=[],
        summary="Latest paper run has 8 replayable core events.",
        latest_replay=EventLedgerReplay(
            run_id="00000000-0000-0000-0000-000000000014",
            event_count=8,
            chain_count=1,
            chains=[
                EventLedgerReplayChain(
                    correlation_id="core-chain",
                    ticker="NVDA",
                    topics=["market_event", "strategy_input", "trade_intent", "order_state"],
                    order_states=["new", "validated", "risk_approved", "sent", "filled"],
                    terminal_state="filled",
                    event_count=8,
                )
            ],
        ),
    )
    monkeypatch.setattr(mvp, "get_event_ledger_status", lambda session: status, raising=False)
    client = TestClient(create_app())

    response = client.get("/api/mvp/paper-trading/event-ledger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_event_count"] == 8
    assert payload["latest_run_status"] == "completed"
    assert payload["latest_replay"]["chains"][0]["terminal_state"] == "filled"


def alpha_snapshot_payload(*, trading_day: str) -> AlphaValidationSnapshotPayload:
    return AlphaValidationSnapshotPayload(
        id="00000000-0000-0000-0000-000000000061",
        team_id="00000000-0000-0000-0000-000000000062",
        strategy_id="deterministic_watchlist_v1",
        trading_day=trading_day,
        alpha_ready=False,
        validation_level="collecting",
        blockers=["closed_trade_sample"],
        review_day_count=5,
        consecutive_positive_expectancy_days=4,
        filled_order_count=20,
        closed_trade_count=6,
        event_chain_count=3,
        latest_expectancy=42.5,
        average_expectancy=25.0,
        max_drawdown=0.03,
        created_at="2026-06-14T00:00:00+00:00",
        updated_at="2026-06-14T00:00:00+00:00",
    )


def strategy_competition_payload() -> StrategyCompetitionPayload:
    return StrategyCompetitionPayload(
        trading_day="2026-06-14",
        status="allocation_ready",
        active_strategy_id="deterministic_watchlist_v1",
        selected_strategy_id="deterministic_watchlist_v1",
        strategy_count=2,
        allocatable_strategy_count=1,
        competition_ready=False,
        entries=[
            StrategyCompetitionEntryPayload(
                strategy_id="deterministic_watchlist_v1",
                name="Deterministic Watchlist Strategy",
                version="v1",
                source="paper_core",
                execution_mode="paper",
                status="active",
                rank=1,
                ranking_score=80.0,
                allocation_weight=1.0,
                eligible_for_allocation=True,
                recommended_action="allocate_paper_capital",
                blockers=[],
                readiness="paper_ready",
                promotion_gate="eligible_for_shadow",
                sample_size=42,
                filled_order_count=40,
                observed_pnl=125.0,
                primary_regime="range_market",
                signal_quality_score=0.7,
                supports_live=False,
                supports_hot_swap=True,
            ),
            StrategyCompetitionEntryPayload(
                strategy_id="moving_average_cross",
                name="MovingAverageCross",
                version="catalog",
                source="lean_catalog",
                execution_mode="backtest",
                status="available",
                rank=2,
                ranking_score=0.0,
                allocation_weight=0.0,
                eligible_for_allocation=False,
                recommended_action="keep_in_lab",
                blockers=["not_connected_to_paper_runtime"],
                readiness="backtest_only",
                promotion_gate="not_connected_to_paper_runtime",
                sample_size=0,
                filled_order_count=0,
                observed_pnl=0.0,
                primary_regime="backtest_only",
                signal_quality_score=0.0,
                supports_live=False,
                supports_hot_swap=False,
            ),
        ],
        summary="Strategy competition fixture.",
    )
