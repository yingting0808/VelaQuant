from collections.abc import Iterator
from dataclasses import asdict
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.llm import build_openai_research_client, build_openai_research_status
from app.ai.workflow import run_research_workflow
from app.core.config import get_settings
from app.data.providers.base import MarketDataProvider
from app.data.providers.registry import build_market_data_provider
from app.db.session import get_session
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.event_ledger import get_event_ledger_status
from app.services.lean_backtest import (
    BacktestParameterValidationError,
    read_backtest_history,
    read_latest_backtest,
    run_lean_backtest,
)
from app.services.strategy_candidate_backtest import run_strategy_candidate_backtests
from app.services.paper_trading import (
    PaperOrderCreate,
    get_paper_trading_summary,
    list_paper_run_events,
    list_paper_runs,
    run_daily_paper_trading_loop,
    submit_paper_order,
)
from app.services.paper_scheduler import get_paper_scheduler_status
from app.services.market_calendar import get_market_session_status
from app.services.paper_action_plan import get_paper_action_plan
from app.services.paper_action_executor import (
    execute_paper_primary_action,
    queue_paper_primary_action,
    should_queue_paper_primary_action,
)
from app.services.paper_operations import (
    get_paper_operations_history,
    get_paper_operations_status,
    quarantine_legacy_manual_future_runs,
    repair_paper_operations_event_ledger,
)
from app.services.paper_daily_report import get_paper_daily_report
from app.services.paper_execution_diagnostics import get_paper_execution_diagnostics
from app.services.paper_risk_profile import get_paper_risk_profile
from app.services.paper_risk_limit_review import get_paper_risk_limit_review
from app.services.paper_risk_settings import apply_paper_risk_limit_recommendation
from app.services.paper_review_trend import get_paper_review_trend
from app.services.paper_simulation import PaperSimulationRequest, run_paper_simulation_lab
from app.services.paper_strategy_reviews import get_paper_strategy_reviews
from app.services.portfolio import PositionInput, calculate_exposure
from app.services.research_notebook import ResearchNoteCreate, save_research_result_as_note
from app.services.runtime_settings import (
    RuntimeSettingsUpdate,
    get_effective_settings,
    get_runtime_settings_payload,
    update_runtime_settings,
)
from app.services.alpha_validation import get_alpha_validation
from app.services.alpha_gate_progress import get_alpha_gate_progress
from app.services.alpha_validation_snapshot import get_alpha_validation_snapshots, record_alpha_validation_snapshot
from app.services.alpha_validation_forecast import get_alpha_validation_forecast
from app.services.live_small_review import get_live_small_review_packet
from app.services.shadow_daily_report import get_shadow_daily_report
from app.services.shadow_review import get_shadow_review_packet
from app.services.shadow_observation import get_shadow_observations, record_shadow_observation
from app.services.shadow_observation_health import get_shadow_observation_health
from app.services.shadow_validation import get_shadow_validation
from app.services.strategy_lifecycle_approval import (
    StrategyKillApprovalRequest,
    StrategyLiveSmallApprovalRequest,
    StrategyShadowApprovalRequest,
    approve_strategy_kill,
    approve_live_small_promotion,
    approve_shadow_promotion,
    reconcile_lifecycle_with_alpha_validation,
)
from app.services.strategy_catalog import UnknownStrategyError, load_enabled_strategies
from app.services.strategy_control import DEFAULT_PAPER_STRATEGY_ID, assert_strategy_execution_allowed, get_strategy_execution_binding
from app.services.strategy_attribution import attribute_current_paper_strategy
from app.services.strategy_evaluation import evaluate_current_paper_strategy
from app.services.strategy_lab import get_strategy_lab_status
from app.services.strategy_lifecycle import get_strategy_lifecycle
from app.services.strategy_lifecycle_audit import get_strategy_lifecycle_audit
from app.services.strategy_registry import get_strategy_registry
from app.services.strategy_competition import (
    get_strategy_competition,
    get_strategy_competition_snapshots,
    record_strategy_competition_snapshot,
)
from app.services.strategy_alpha_isolation import get_strategy_alpha_isolation
from app.services.strategy_runtime import get_strategy_runtime_status
from app.services.strategy_versions import (
    activate_strategy_version,
    get_strategy_version_control,
    register_strategy_version,
    rollback_strategy_version,
)
from app.services.trading_system_readiness import get_trading_system_readiness
from app.services.execution_accounts import get_or_create_strategy_execution_accounts
from app.services.workspace import (
    NoteCreate,
    PositionUpsert,
    WatchlistUpsert,
    create_note,
    delete_position,
    delete_watchlist_item,
    get_portfolio_payload,
    get_workspace_summary,
    import_positions_csv,
    list_notes,
    list_watchlist_items,
    upsert_position,
    upsert_watchlist_item,
)
from app.trading_core.engine import TradingEngine
from app.trading_core.event_bus import build_event_bus
from app.trading_core.events import MarketEvent
from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskEngine, RiskLimits

router = APIRouter(prefix="/api/mvp", tags=["mvp"])


class ResearchBody(BaseModel):
    ticker: str = Field(min_length=1)
    question: str = Field(min_length=1)

    @field_validator("ticker", "question")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class BacktestBody(BaseModel):
    strategy_id: str = Field(min_length=1)
    parameters: dict[str, str] = Field(default_factory=dict)

    @field_validator("strategy_id")
    @classmethod
    def strip_strategy_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class CandidateBacktestBody(BaseModel):
    strategy_id: str = Field(default=DEFAULT_PAPER_STRATEGY_ID, min_length=1)
    tickers: list[str] = Field(min_length=2)
    parameters: dict[str, str] = Field(default_factory=dict)

    @field_validator("strategy_id")
    @classmethod
    def strip_candidate_strategy_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class ImportPositionsBody(BaseModel):
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class TradingCoreDryRunBody(BaseModel):
    event: MarketEvent
    portfolio: PortfolioState
    watchlist: list[str] = Field(default_factory=list)
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    strategy_notional: float | None = Field(default=None, gt=0)
    strategy_id: str = Field(default=DEFAULT_PAPER_STRATEGY_ID, min_length=1)


class StrategyVersionRegisterBody(BaseModel):
    strategy_id: str = Field(default=DEFAULT_PAPER_STRATEGY_ID, min_length=1)
    version: str = Field(min_length=1)
    parameters_json: str = "{}"


class StrategyVersionActivateBody(BaseModel):
    strategy_id: str = Field(default=DEFAULT_PAPER_STRATEGY_ID, min_length=1)
    version: str = Field(min_length=1)
    reason: str = Field(default="manual activation", min_length=1)


class StrategyVersionRollbackBody(BaseModel):
    strategy_id: str = Field(default=DEFAULT_PAPER_STRATEGY_ID, min_length=1)


def get_market_data_provider(session: Session = Depends(get_session)) -> Iterator[MarketDataProvider]:
    provider = build_market_data_provider(get_effective_settings(session, get_settings()))
    try:
        yield provider
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


@router.get("/dashboard")
def dashboard(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_effective_settings(session, get_settings())
    portfolio = get_portfolio_payload(session, provider)
    alerts = generate_event_alerts(
        portfolio_tickers=[item.ticker for item in portfolio.positions],
        candidates=[
            AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="mock_sec"),
            AlertCandidate(ticker="NVDA", title="NVDA news", reason="News event", source="mock_news"),
        ],
    )
    return {
        "portfolio": {
            "name": portfolio.name,
            "total_market_value": portfolio.total_market_value,
            "positions": [item.model_dump() for item in portfolio.positions],
        },
        "alerts": [alert.model_dump() for alert in alerts],
        "ai_prompts": [
            "解释当前页面",
            "识别组合风险",
            "生成多/中/空情景",
            "起草交易计划",
        ],
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
        "strategy_lab": get_strategy_lab_status().model_dump(),
    }


@router.get("/data-sources/status")
def data_sources_status(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_effective_settings(session, get_settings())
    return {
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }


@router.get("/workspace")
def workspace_summary(session: Session = Depends(get_session)) -> dict:
    return get_workspace_summary(session).model_dump()


@router.get("/portfolio")
def portfolio_workspace(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_portfolio_payload(session, provider).model_dump()


@router.put("/portfolio/positions")
def portfolio_upsert_position(body: PositionUpsert, session: Session = Depends(get_session)) -> dict:
    return upsert_position(session, body).model_dump()


@router.delete("/portfolio/positions/{ticker}")
def portfolio_delete_position(ticker: str = Path(min_length=1), session: Session = Depends(get_session)) -> dict:
    try:
        deleted = delete_position(session, ticker)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return deleted.model_dump()


@router.post("/portfolio/import")
def portfolio_import_positions(
    body: ImportPositionsBody,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return import_positions_csv(session, body.content, provider=provider).model_dump()


@router.get("/watchlist")
def watchlist_workspace(session: Session = Depends(get_session)) -> dict:
    return {"items": [item.model_dump() for item in list_watchlist_items(session)]}


@router.post("/watchlist")
def watchlist_upsert(body: WatchlistUpsert, session: Session = Depends(get_session)) -> dict:
    return upsert_watchlist_item(session, body).model_dump()


@router.delete("/watchlist/{ticker}")
def watchlist_delete(ticker: str = Path(min_length=1), session: Session = Depends(get_session)) -> dict:
    try:
        deleted = delete_watchlist_item(session, ticker)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return deleted.model_dump()


@router.get("/notes")
def notes_workspace(session: Session = Depends(get_session)) -> dict:
    return {"notes": [note.model_dump() for note in list_notes(session)]}


@router.post("/notes")
def notes_create(body: NoteCreate, session: Session = Depends(get_session)) -> dict:
    return create_note(session, body).model_dump()


@router.post("/research/notes")
def research_note_create(body: ResearchNoteCreate, session: Session = Depends(get_session)) -> dict:
    return save_research_result_as_note(session, body).model_dump()


@router.get("/paper-trading/summary")
def paper_trading_summary(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_paper_trading_summary(session, provider).model_dump()


@router.get("/paper-trading/daily-report")
def paper_trading_daily_report(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_paper_daily_report(session, provider).model_dump()


@router.post("/paper-trading/daily-run")
def paper_trading_daily_run(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return run_daily_paper_trading_loop(session, provider).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/paper-trading/orders")
def paper_trading_order(
    body: PaperOrderCreate,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    try:
        assert_strategy_execution_allowed(session, body.strategy_id, requested_mode="paper")
        order = submit_paper_order(session, provider, body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return order.model_dump()


@router.get("/paper-trading/scheduler")
def paper_trading_scheduler_status() -> dict:
    return get_paper_scheduler_status().model_dump()


@router.get("/paper-trading/market-session")
def paper_trading_market_session() -> dict:
    return asdict(get_market_session_status())


@router.get("/paper-trading/operations")
def paper_trading_operations_status(session: Session = Depends(get_session)) -> dict:
    return get_paper_operations_status(session).model_dump()


@router.get("/paper-trading/operations/history")
def paper_trading_operations_history(session: Session = Depends(get_session)) -> dict:
    return get_paper_operations_history(session).model_dump()


@router.post("/paper-trading/operations/repair-ledger")
def paper_trading_repair_event_ledger(session: Session = Depends(get_session)) -> dict:
    return repair_paper_operations_event_ledger(session).model_dump()


@router.post("/paper-trading/operations/quarantine-legacy-runs")
def paper_trading_quarantine_legacy_runs(session: Session = Depends(get_session)) -> dict:
    return quarantine_legacy_manual_future_runs(session).model_dump()


@router.get("/paper-trading/review-trend")
def paper_trading_review_trend(session: Session = Depends(get_session)) -> dict:
    return get_paper_review_trend(session).model_dump()


@router.post("/paper-trading/simulation/run")
def paper_trading_simulation_run(
    body: PaperSimulationRequest,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return run_paper_simulation_lab(session, provider, body).model_dump()


@router.get("/paper-trading/execution-diagnostics")
def paper_trading_execution_diagnostics(session: Session = Depends(get_session)) -> dict:
    return get_paper_execution_diagnostics(session).model_dump()


@router.get("/paper-trading/risk-profile")
def paper_trading_risk_profile(session: Session = Depends(get_session)) -> dict:
    return get_paper_risk_profile(session).model_dump()


@router.get("/paper-trading/risk-limit-review")
def paper_trading_risk_limit_review(session: Session = Depends(get_session)) -> dict:
    return get_paper_risk_limit_review(session).model_dump()


@router.post("/paper-trading/risk-limit-review/apply-paper-recommendation")
def paper_trading_apply_risk_limit_recommendation(session: Session = Depends(get_session)) -> dict:
    return apply_paper_risk_limit_recommendation(session).model_dump()


@router.get("/paper-trading/action-plan")
def paper_trading_action_plan(session: Session = Depends(get_session)) -> dict:
    return get_paper_action_plan(session).model_dump()


@router.post("/paper-trading/action-plan/execute-primary")
def paper_trading_execute_primary_action(
    background_tasks: BackgroundTasks,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    try:
        plan = get_paper_action_plan(session)
        if should_queue_paper_primary_action(plan.primary_action):
            return queue_paper_primary_action(session, background_tasks).model_dump()
        return execute_paper_primary_action(session, provider).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/paper-trading/strategy-reviews")
def paper_trading_strategy_reviews(session: Session = Depends(get_session)) -> dict:
    return get_paper_strategy_reviews(session).model_dump(mode="json")


@router.get("/paper-trading/runs")
def paper_trading_runs(session: Session = Depends(get_session)) -> dict:
    return {"runs": [run.model_dump() for run in list_paper_runs(session)]}


@router.get("/paper-trading/runs/{run_id}/events")
def paper_trading_run_events(run_id: UUID, session: Session = Depends(get_session)) -> dict:
    return {"events": [event.model_dump() for event in list_paper_run_events(session, run_id)]}


@router.get("/paper-trading/event-ledger")
def paper_trading_event_ledger(session: Session = Depends(get_session)) -> dict:
    return get_event_ledger_status(session).model_dump()


@router.post("/trading-core/dry-run")
def trading_core_dry_run(body: TradingCoreDryRunBody, session: Session = Depends(get_session)) -> dict:
    workspace = get_workspace_summary(session)
    try:
        assert_strategy_execution_allowed(session, body.strategy_id, requested_mode="paper")
        binding = get_strategy_execution_binding(
            session,
            workspace.team_id,
            body.strategy_id,
            notional=body.strategy_notional,
        )
        risk_engine = RiskEngine(body.risk_limits)
        settings = get_settings()
        event_bus = build_event_bus(
            mode=settings.event_bus_mode,
            redis_url=settings.redis_url,
            stream_name=settings.redis_stream_name,
        )
        engine = TradingEngine(strategy_binding=binding, risk_engine=risk_engine, event_bus=event_bus)
        return engine.process_event(body.event, body.portfolio).model_dump(mode="json")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/strategy-lab/status")
def strategy_lab_status() -> dict:
    return get_strategy_lab_status().model_dump()


@router.get("/strategy-lab/evaluation")
def strategy_lab_evaluation(session: Session = Depends(get_session)) -> dict:
    return evaluate_current_paper_strategy(session).model_dump()


@router.get("/strategy-lab/attribution")
def strategy_lab_attribution(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return attribute_current_paper_strategy(session, provider=provider).model_dump()


@router.get("/strategy-lab/registry")
def strategy_lab_registry(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_strategy_registry(session, provider=provider).model_dump()


@router.get("/strategy-lab/competition")
def strategy_lab_competition(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return get_strategy_competition(session, provider=provider).model_dump()


@router.post("/strategy-lab/competition/snapshot")
def strategy_lab_competition_snapshot(
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    return record_strategy_competition_snapshot(session, provider=provider).model_dump()


@router.get("/strategy-lab/competition/snapshots")
def strategy_lab_competition_snapshots(session: Session = Depends(get_session)) -> dict:
    return get_strategy_competition_snapshots(session).model_dump()


@router.get("/strategy-lab/lifecycle")
def strategy_lab_lifecycle(session: Session = Depends(get_session)) -> dict:
    return get_strategy_lifecycle(session).model_dump()


@router.get("/strategy-lab/lifecycle/audit")
def strategy_lab_lifecycle_audit(session: Session = Depends(get_session)) -> dict:
    return get_strategy_lifecycle_audit(session).model_dump()


@router.get("/strategy-lab/system-readiness")
def strategy_lab_system_readiness(session: Session = Depends(get_session)) -> dict:
    return get_trading_system_readiness(session).model_dump()


@router.get("/strategy-lab/alpha-isolation")
def strategy_lab_alpha_isolation(session: Session = Depends(get_session)) -> dict:
    return get_strategy_alpha_isolation(session).model_dump()


@router.get("/strategy-lab/alpha-validation")
def strategy_lab_alpha_validation(session: Session = Depends(get_session)) -> dict:
    return get_alpha_validation(session).model_dump()


@router.get("/strategy-lab/alpha-gates")
def strategy_lab_alpha_gates(session: Session = Depends(get_session)) -> dict:
    return get_alpha_gate_progress(session).model_dump()


@router.get("/strategy-lab/alpha-snapshots")
def strategy_lab_alpha_snapshots(session: Session = Depends(get_session)) -> dict:
    return get_alpha_validation_snapshots(session).model_dump()


@router.post("/strategy-lab/alpha-snapshots/record")
def strategy_lab_record_alpha_snapshot(session: Session = Depends(get_session)) -> dict:
    return record_alpha_validation_snapshot(session).model_dump()


@router.get("/strategy-lab/alpha-forecast")
def strategy_lab_alpha_forecast(session: Session = Depends(get_session)) -> dict:
    return get_alpha_validation_forecast(session).model_dump()


@router.get("/strategy-lab/shadow-review")
def strategy_lab_shadow_review(session: Session = Depends(get_session)) -> dict:
    return get_shadow_review_packet(session).model_dump()


@router.get("/strategy-lab/shadow-observations")
def strategy_lab_shadow_observations(session: Session = Depends(get_session)) -> dict:
    return get_shadow_observations(session).model_dump()


@router.post("/strategy-lab/shadow-observations/record")
def strategy_lab_record_shadow_observation(session: Session = Depends(get_session)) -> dict:
    try:
        return record_shadow_observation(session).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/strategy-lab/shadow-validation")
def strategy_lab_shadow_validation(session: Session = Depends(get_session)) -> dict:
    return get_shadow_validation(session).model_dump()


@router.get("/strategy-lab/shadow-observation-health")
def strategy_lab_shadow_observation_health(session: Session = Depends(get_session)) -> dict:
    return get_shadow_observation_health(session).model_dump()


@router.get("/strategy-lab/shadow-daily-report")
def strategy_lab_shadow_daily_report(session: Session = Depends(get_session)) -> dict:
    return get_shadow_daily_report(session).model_dump()


@router.get("/strategy-lab/live-small-review")
def strategy_lab_live_small_review(session: Session = Depends(get_session)) -> dict:
    return get_live_small_review_packet(session).model_dump()


@router.post("/strategy-lab/lifecycle/approve-shadow")
def strategy_lab_approve_shadow(
    body: StrategyShadowApprovalRequest,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return approve_shadow_promotion(session, body).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/strategy-lab/lifecycle/approve-live-small")
def strategy_lab_approve_live_small(
    body: StrategyLiveSmallApprovalRequest,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return approve_live_small_promotion(session, body).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/strategy-lab/lifecycle/approve-kill")
def strategy_lab_approve_kill(
    body: StrategyKillApprovalRequest,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return approve_strategy_kill(session, body).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/strategy-lab/lifecycle/reconcile")
def strategy_lab_reconcile_lifecycle(session: Session = Depends(get_session)) -> dict:
    try:
        return reconcile_lifecycle_with_alpha_validation(session).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/strategy-lab/version-control")
def strategy_lab_version_control(session: Session = Depends(get_session)) -> dict:
    return get_strategy_version_control(session).model_dump()


@router.post("/strategy-lab/version-control/versions")
def strategy_lab_register_version(body: StrategyVersionRegisterBody, session: Session = Depends(get_session)) -> dict:
    try:
        return register_strategy_version(
            session,
            strategy_id=body.strategy_id,
            version=body.version,
            parameters_json=body.parameters_json,
        ).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/strategy-lab/version-control/activate")
def strategy_lab_activate_version(body: StrategyVersionActivateBody, session: Session = Depends(get_session)) -> dict:
    try:
        return activate_strategy_version(
            session,
            strategy_id=body.strategy_id,
            version=body.version,
            reason=body.reason,
        ).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/strategy-lab/version-control/rollback")
def strategy_lab_rollback_version(body: StrategyVersionRollbackBody, session: Session = Depends(get_session)) -> dict:
    try:
        return rollback_strategy_version(session, strategy_id=body.strategy_id).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/strategy-lab/runtime")
def strategy_lab_runtime(session: Session = Depends(get_session)) -> dict:
    return get_strategy_runtime_status(session).model_dump()


@router.get("/strategy-lab/execution-accounts")
def strategy_lab_execution_accounts(
    strategy_id: str = DEFAULT_PAPER_STRATEGY_ID,
    session: Session = Depends(get_session),
) -> dict:
    workspace = get_workspace_summary(session)
    return {
        "accounts": [
            account.model_dump()
            for account in get_or_create_strategy_execution_accounts(
                session,
                team_id=workspace.team_id,
                strategy_id=strategy_id,
            )
        ]
    }


@router.get("/ai/status")
def ai_status(session: Session = Depends(get_session)) -> dict:
    effective_settings = get_effective_settings(session, get_settings())
    return {
        "langgraph": {
            "available": True,
            "mode": "research_workflow",
            "message": "LangGraph is used for research workflow orchestration only.",
        },
        "research_llm": build_openai_research_status(effective_settings).model_dump(),
        "execution_path": {
            "ai_generates_trade_intent": False,
            "ai_influences_risk": False,
            "ai_calls_execution": False,
        },
    }


@router.get("/runtime-settings")
def runtime_settings(session: Session = Depends(get_session)) -> dict:
    return get_runtime_settings_payload(session, get_settings()).model_dump()


@router.put("/runtime-settings")
def runtime_settings_update(body: RuntimeSettingsUpdate, session: Session = Depends(get_session)) -> dict:
    return update_runtime_settings(session, body, get_settings()).model_dump()


@router.get("/strategy-lab/strategies")
def strategy_lab_strategies() -> dict:
    return {"strategies": [strategy.public_payload() for strategy in load_enabled_strategies()]}


@router.post("/strategy-lab/backtests")
def strategy_lab_run_backtest(body: BacktestBody, session: Session = Depends(get_session)) -> dict:
    try:
        effective_settings = get_effective_settings(session, get_settings())
        result = run_lean_backtest(
            body.strategy_id,
            parameter_overrides=body.parameters,
            timeout_seconds=effective_settings.lean_backtest_timeout_seconds,
        )
    except UnknownStrategyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BacktestParameterValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result.model_dump()


@router.post("/strategy-lab/candidate-backtests")
def strategy_lab_run_candidate_backtests(
    body: CandidateBacktestBody,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    try:
        result = run_strategy_candidate_backtests(
            strategy_id=body.strategy_id,
            tickers=body.tickers,
            parameter_overrides=body.parameters,
            market_data_provider=provider,
        )
    except UnknownStrategyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except BacktestParameterValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return result.model_dump()


@router.get("/strategy-lab/backtests/latest")
def strategy_lab_latest_backtest() -> dict:
    latest = read_latest_backtest()
    return {"latest": latest.model_dump() if latest is not None else None}


@router.get("/strategy-lab/backtests/history")
def strategy_lab_backtest_history(limit: int = 10) -> dict:
    history = read_backtest_history(limit=limit)
    return {"history": [item.model_dump() for item in history]}


def _normalize_path_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")
    return normalized


@router.get("/market/quote/{ticker}")
def market_quote(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    normalized = _normalize_path_ticker(ticker)
    return provider.get_quote(normalized).model_dump()


@router.get("/market/history/{ticker}")
def market_history(
    ticker: str = Path(min_length=1),
    interval: Literal["1d", "1W", "1M"] = "1d",
    start_date: str | None = None,
    end_date: str | None = None,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> list[dict]:
    normalized = _normalize_path_ticker(ticker)
    return [
        bar.model_dump()
        for bar in provider.get_price_history(
            normalized,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
    ]


@router.get("/market/fundamentals/{ticker}")
def market_fundamentals(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    normalized = _normalize_path_ticker(ticker)
    return provider.get_fundamentals(normalized).model_dump()


@router.get("/market/snapshot/{ticker}")
def market_snapshot(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_effective_settings(session, get_settings())
    normalized = _normalize_path_ticker(ticker)
    snapshot = provider.get_market_snapshot(normalized)
    return {
        "ticker": snapshot.ticker,
        "quote": snapshot.quote.model_dump(),
        "fundamentals": snapshot.fundamentals.model_dump(),
        "history": [bar.model_dump() for bar in snapshot.history],
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }


@router.post("/research")
def research(
    body: ResearchBody,
    provider: MarketDataProvider = Depends(get_market_data_provider),
    session: Session = Depends(get_session),
) -> dict:
    evidence = [
        EvidenceItemInput(
            title=item.title,
            summary=item.summary,
            source=item.source,
            source_url=item.source_url,
        )
        for item in provider.get_research_evidence(body.ticker)
    ]
    effective_settings = get_effective_settings(session, get_settings())
    result = run_research_workflow(
        ResearchRequest(ticker=body.ticker, question=body.question, evidence=evidence),
        llm_client=build_openai_research_client(effective_settings),
    )
    return result.model_dump()
