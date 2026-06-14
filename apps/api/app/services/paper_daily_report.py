from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import PaperRun, PaperRunTrigger
from app.data.providers.base import MarketDataProvider
from app.services.alpha_gate_progress import AlphaGateProgressItem, build_alpha_gate_progress
from app.services.alpha_validation import get_alpha_validation
from app.services.alpha_validation_forecast import build_alpha_validation_forecast
from app.services.event_ledger import get_event_ledger_status
from app.services.paper_operations import get_paper_operations_status
from app.services.paper_review_trend import get_paper_review_trend
from app.services.paper_scheduler import get_paper_scheduler_status
from app.services.paper_trading import get_paper_trading_summary


class PaperDailyReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trading_day: str
    run_state: str
    health_status: str
    recommended_action: str
    scheduler_running: bool
    scheduler_next_run_at: datetime | None
    scheduler_next_run_will_execute: bool | None
    scheduler_next_run_execution_gate: str | None
    scheduler_next_actionable_run_at: datetime | None
    scheduler_next_actionable_trading_day: str | None
    scheduler_next_actionable_execution_gate: str | None
    estimated_sessions_to_alpha_ready: int | None
    limiting_alpha_gate: str | None
    account_equity: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    daily_pnl: float
    daily_return: float
    candidate_count: int
    actionable_candidate_count: int
    ordered_candidate_count: int
    dismissed_candidate_count: int
    order_count: int
    open_position_count: int
    latest_expectancy: float
    average_expectancy: float
    consecutive_positive_expectancy_days: int
    event_ledger_ready: bool
    alpha_ready: bool
    alpha_blockers: list[str]
    open_alpha_gates: list[AlphaGateProgressItem]
    data_quality_warnings: list[str]
    summary: str


def get_paper_daily_report(session: Session, provider: MarketDataProvider) -> PaperDailyReportPayload:
    operations = get_paper_operations_status(session)
    trading_day = operations.trading_day
    trading_summary = get_paper_trading_summary(session, provider, as_of_trading_day=trading_day)
    review_trend = get_paper_review_trend(session, as_of_trading_day=trading_day)
    scheduler = get_paper_scheduler_status()
    event_ledger = get_event_ledger_status(session, as_of_trading_day=trading_day)
    alpha_validation = get_alpha_validation(session, as_of_trading_day=trading_day)
    alpha_forecast = build_alpha_validation_forecast(alpha_validation)
    alpha_gate_progress = build_alpha_gate_progress(alpha_validation)
    data_quality_warnings = _data_quality_warnings(session, trading_day)
    latest_trend_item = review_trend.items[0] if review_trend.items else None
    candidate_status_counts = _candidate_status_counts(trading_summary.candidates)
    return PaperDailyReportPayload(
        trading_day=trading_day,
        run_state=operations.run_state,
        health_status=operations.health_status,
        recommended_action=operations.recommended_action,
        scheduler_running=scheduler.running,
        scheduler_next_run_at=scheduler.next_run_at,
        scheduler_next_run_will_execute=scheduler.next_run_will_execute,
        scheduler_next_run_execution_gate=scheduler.next_run_execution_gate,
        scheduler_next_actionable_run_at=scheduler.next_actionable_run_at,
        scheduler_next_actionable_trading_day=scheduler.next_actionable_trading_day,
        scheduler_next_actionable_execution_gate=scheduler.next_actionable_execution_gate,
        estimated_sessions_to_alpha_ready=alpha_forecast.estimated_sessions_to_alpha_ready,
        limiting_alpha_gate=alpha_forecast.limiting_gate,
        account_equity=round(trading_summary.account.equity, 2),
        cash=round(trading_summary.account.cash, 2),
        realized_pnl=round(trading_summary.account.realized_pnl, 2),
        unrealized_pnl=round(trading_summary.account.unrealized_pnl, 2),
        daily_pnl=latest_trend_item.daily_pnl if latest_trend_item is not None else 0.0,
        daily_return=latest_trend_item.daily_return if latest_trend_item is not None else 0.0,
        candidate_count=len(trading_summary.candidates),
        actionable_candidate_count=candidate_status_counts["proposed"],
        ordered_candidate_count=candidate_status_counts["ordered"],
        dismissed_candidate_count=candidate_status_counts["dismissed"],
        order_count=len(trading_summary.orders),
        open_position_count=len(trading_summary.positions),
        latest_expectancy=review_trend.latest_expectancy,
        average_expectancy=review_trend.average_expectancy,
        consecutive_positive_expectancy_days=review_trend.consecutive_positive_expectancy_days,
        event_ledger_ready=event_ledger.replay_ready,
        alpha_ready=alpha_validation.alpha_ready,
        alpha_blockers=alpha_validation.blockers,
        open_alpha_gates=[item for item in alpha_gate_progress.items if not item.passed],
        data_quality_warnings=data_quality_warnings,
        summary=_summary(
            health_status=operations.health_status,
            run_state=operations.run_state,
            latest_expectancy=review_trend.latest_expectancy,
            alpha_ready=alpha_validation.alpha_ready,
        ),
    )


def _candidate_status_counts(candidates) -> dict[str, int]:
    counts = {"proposed": 0, "ordered": 0, "dismissed": 0}
    for candidate in candidates:
        status = str(getattr(candidate, "status", "") or "").strip().lower()
        if status in counts:
            counts[status] += 1
    return counts


def _data_quality_warnings(session: Session, trading_day: str) -> list[str]:
    future_run = session.exec(
        select(PaperRun)
        .where(PaperRun.trading_day > trading_day)
        .where(PaperRun.trigger != PaperRunTrigger.simulation)
    ).first()
    if future_run is None:
        return []
    return ["future_runs_excluded_from_as_of_report"]


def _summary(
    *,
    health_status: str,
    run_state: str,
    latest_expectancy: float,
    alpha_ready: bool,
) -> str:
    if alpha_ready:
        return "Daily paper report: operations are healthy and paper alpha gates are satisfied."
    return (
        "Daily paper report: "
        f"operations {health_status}, run {run_state}, latest expectancy {latest_expectancy:.2f}; "
        "continue paper validation before live capital."
    )
