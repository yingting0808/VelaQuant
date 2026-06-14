from datetime import datetime, timezone
import json

from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.data.providers.registry import build_market_data_provider
from app.db.session import engine
from app.domain.models import CoreEventLog, PaperRunTrigger
from app.services.market_calendar import MarketSessionStatus, get_market_session_status
from app.services.paper_trading import run_daily_paper_trading_loop
from app.services.shadow_observation import record_shadow_observation
from app.services.workspace import get_or_create_default_workspace


class PaperSchedulerStatus(BaseModel):
    enabled: bool
    running: bool
    job_count: int
    job_id: str
    cron: str
    timezone: str
    next_run_at: datetime | None
    next_run_will_execute: bool | None = None
    next_run_execution_gate: str | None = None
    next_run_trading_day: str | None = None
    next_run_gate_reason: str | None = None
    next_actionable_run_at: datetime | None = None
    next_actionable_trading_day: str | None = None
    next_actionable_execution_gate: str | None = None
    next_actionable_gate_reason: str | None = None
    last_checked_at: datetime
    can_run_now: bool
    execution_gate: str
    market_date: str
    trading_day: str
    is_market_session: bool
    session_closed: bool
    calendar_provider: str
    gate_reason: str


class PaperScheduledRunResult(BaseModel):
    executed: bool
    market_date: str
    trading_day: str
    is_market_session: bool
    session_closed: bool
    calendar_provider: str
    reason: str
    summary: str


_scheduler = None
PAPER_TRADING_DAILY_JOB_ID = "paper_trading_daily_run"


def start_paper_scheduler(settings: Settings | None = None):
    global _scheduler
    settings = settings or get_settings()
    if not settings.paper_scheduler_enabled:
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone=settings.paper_scheduler_timezone)
    scheduler.add_job(
        run_scheduled_paper_trading_once,
        CronTrigger.from_crontab(settings.paper_scheduler_cron, timezone=settings.paper_scheduler_timezone),
        id=PAPER_TRADING_DAILY_JOB_ID,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_paper_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def get_paper_scheduler_status(settings: Settings | None = None) -> PaperSchedulerStatus:
    settings = settings or get_settings()
    job = _scheduler.get_job(PAPER_TRADING_DAILY_JOB_ID) if _scheduler is not None else None
    next_run_at = job.next_run_time if job is not None else None
    market_status = get_market_session_status()
    next_market_status = get_market_session_status(now=next_run_at) if next_run_at is not None else None
    next_actionable_run_at, next_actionable_market_status = _next_actionable_run(job, next_run_at)
    can_run_now = market_status.is_market_session and market_status.session_closed
    return PaperSchedulerStatus(
        enabled=settings.paper_scheduler_enabled,
        running=bool(_scheduler is not None and _scheduler.running),
        job_count=len(_scheduler.get_jobs()) if _scheduler is not None else 0,
        job_id=PAPER_TRADING_DAILY_JOB_ID,
        cron=settings.paper_scheduler_cron,
        timezone=settings.paper_scheduler_timezone,
        next_run_at=next_run_at,
        next_run_will_execute=(
            next_market_status.is_market_session and next_market_status.session_closed
            if next_market_status is not None
            else None
        ),
        next_run_execution_gate=_execution_gate(next_market_status) if next_market_status is not None else None,
        next_run_trading_day=next_market_status.trading_day if next_market_status is not None else None,
        next_run_gate_reason=next_market_status.reason if next_market_status is not None else None,
        next_actionable_run_at=next_actionable_run_at,
        next_actionable_trading_day=(
            next_actionable_market_status.trading_day if next_actionable_market_status is not None else None
        ),
        next_actionable_execution_gate=(
            _execution_gate(next_actionable_market_status) if next_actionable_market_status is not None else None
        ),
        next_actionable_gate_reason=(
            next_actionable_market_status.reason if next_actionable_market_status is not None else None
        ),
        last_checked_at=datetime.now(timezone.utc),
        can_run_now=can_run_now,
        execution_gate=_execution_gate(market_status),
        market_date=market_status.market_date,
        trading_day=market_status.trading_day,
        is_market_session=market_status.is_market_session,
        session_closed=market_status.session_closed,
        calendar_provider=market_status.calendar_provider,
        gate_reason=market_status.reason,
    )


def _next_actionable_run(job, next_run_at: datetime | None) -> tuple[datetime | None, MarketSessionStatus | None]:
    if job is None or next_run_at is None:
        return None, None

    run_at = next_run_at
    for _ in range(14):
        market_status = get_market_session_status(now=run_at)
        if market_status.is_market_session and market_status.session_closed:
            return run_at, market_status
        trigger = getattr(job, "trigger", None)
        get_next_fire_time = getattr(trigger, "get_next_fire_time", None)
        if not callable(get_next_fire_time):
            return None, None
        following_run_at = get_next_fire_time(run_at, run_at)
        if following_run_at is None or following_run_at == run_at:
            return None, None
        run_at = following_run_at
    return None, None


def run_scheduled_paper_trading_once() -> PaperScheduledRunResult:
    market_status = get_market_session_status()
    if not market_status.is_market_session or not market_status.session_closed:
        result = _scheduled_result(
            market_status,
            executed=False,
            summary=(
                "Scheduled paper trading skipped because the market session is not eligible "
                f"for execution: {market_status.reason}."
            ),
        )
        with Session(engine) as session:
            _persist_scheduler_decision(session, market_status, result)
            session.commit()
        return result

    settings = get_settings()
    provider = build_market_data_provider(settings)
    try:
        with Session(engine) as session:
            run_daily_paper_trading_loop(session, provider, trigger=PaperRunTrigger.scheduled)
            try:
                record_shadow_observation(session)
            except ValueError:
                pass
            result = _scheduled_result(
                market_status,
                executed=True,
                summary="Scheduled paper trading completed for the closed market session.",
            )
            _persist_scheduler_decision(session, market_status, result)
            session.commit()
        return result
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


def _scheduled_result(
    market_status: MarketSessionStatus,
    *,
    executed: bool,
    summary: str,
) -> PaperScheduledRunResult:
    return PaperScheduledRunResult(
        executed=executed,
        market_date=market_status.market_date,
        trading_day=market_status.trading_day,
        is_market_session=market_status.is_market_session,
        session_closed=market_status.session_closed,
        calendar_provider=market_status.calendar_provider,
        reason=market_status.reason,
        summary=summary,
    )


def _execution_gate(market_status: MarketSessionStatus) -> str:
    if market_status.is_market_session and market_status.session_closed:
        return "ready_to_run"
    if market_status.is_market_session:
        return "waiting_for_close"
    return "market_closed"


def _persist_scheduler_decision(
    session: Session,
    market_status: MarketSessionStatus,
    result: PaperScheduledRunResult,
) -> None:
    workspace = get_or_create_default_workspace(session)
    sequence = _next_scheduler_decision_sequence(session, workspace.team.id)
    correlation_id = f"paper_scheduler:{market_status.market_date}"
    payload = {
        "executed": result.executed,
        "execution_gate": _execution_gate(market_status),
        "market_date": market_status.market_date,
        "trading_day": market_status.trading_day,
        "is_market_session": market_status.is_market_session,
        "session_closed": market_status.session_closed,
        "calendar_provider": market_status.calendar_provider,
        "reason": market_status.reason,
        "summary": result.summary,
    }
    session.add(
        CoreEventLog(
            team_id=workspace.team.id,
            run_id=None,
            event_id=f"{correlation_id}:{sequence}:scheduler_decision",
            topic="scheduler_decision",
            sequence=sequence,
            correlation_id=correlation_id,
            causation_id=None,
            payload_json=json.dumps(payload, separators=(",", ":")),
        )
    )


def _next_scheduler_decision_sequence(session: Session, team_id) -> int:
    latest = session.exec(
        select(CoreEventLog)
        .where(CoreEventLog.team_id == team_id)
        .where(CoreEventLog.run_id == None)  # noqa: E711
        .where(CoreEventLog.topic == "scheduler_decision")
        .order_by(CoreEventLog.sequence.desc())
    ).first()
    if latest is None:
        return 1
    return latest.sequence + 1
