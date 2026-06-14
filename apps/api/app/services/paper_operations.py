import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperReview, PaperRun, PaperRunStatus, PaperRunTrigger
from app.services.event_ledger import replay_paper_run
from app.services.market_calendar import current_market_trading_day
from app.services.paper_trading import RUNNING_LOCK_STALE_AFTER_MINUTES
from app.services.workspace import get_or_create_default_workspace


PaperOperationsRunState = Literal["not_started", "running", "completed", "skipped", "failed"]
PaperOperationsHealthStatus = Literal["ready", "warning", "blocked"]
PaperSchedulerDecision = Literal["executed", "skipped", "failed"]
PaperOperationsAction = Literal[
    "run_daily_paper_trading",
    "retry_daily_paper_trading",
    "hold_until_next_session",
    "repair_event_ledger",
    "wait_for_running_job",
]


class PaperOperationsStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trading_day: str
    run_state: PaperOperationsRunState
    health_status: PaperOperationsHealthStatus
    latest_run_id: UUID | None
    latest_run_trading_day: str | None
    latest_run_status: str | None
    today_run_id: UUID | None
    review_id: UUID | None
    latest_error: str | None
    can_retry_today: bool
    event_ledger_ready: bool
    latest_run_event_count: int
    legacy_manual_future_run_count: int
    latest_legacy_manual_future_trading_day: str | None
    data_quality_warnings: list[str]
    latest_scheduler_decision: PaperSchedulerDecision | None = None
    latest_scheduler_decision_at: datetime | None = None
    latest_scheduler_decision_trading_day: str | None = None
    latest_scheduler_decision_reason: str | None = None
    latest_scheduler_decision_summary: str | None = None
    blockers: list[str]
    recommended_action: PaperOperationsAction
    summary: str


class PaperOperationsHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trading_day: str
    run_id: UUID
    status: str
    health_status: PaperOperationsHealthStatus
    event_count: int
    has_review: bool
    candidates_count: int
    orders_count: int
    positions_count: int
    blockers: list[str]
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class PaperOperationsHistoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_size: int
    completed_days: int
    failed_days: int
    blocked_days: int
    replayable_days: int
    review_days: int
    completion_rate: float
    replay_rate: float
    latest_health_status: PaperOperationsHealthStatus
    items: list[PaperOperationsHistoryItem]
    summary: str


class PaperOperationsRepairItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    trading_day: str
    status: str
    event_created: bool
    topic: str | None
    reason: str


class PaperOperationsRepairPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_runs: int
    repaired_runs: int
    skipped_runs: int
    items: list[PaperOperationsRepairItem]
    summary: str


class PaperOperationsQuarantineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    trading_day: str
    status: str
    previous_trigger: str
    new_trigger: str
    audit_event_created: bool
    reason: str


class PaperOperationsQuarantinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_runs: int
    quarantined_runs: int
    skipped_runs: int
    items: list[PaperOperationsQuarantineItem]
    summary: str


def get_paper_operations_status(
    session: Session,
    *,
    team_id: UUID | None = None,
    trading_day: str | None = None,
) -> PaperOperationsStatusPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    trading_day = trading_day or _current_trading_day()
    latest_run = _latest_run(session, team_id, as_of_trading_day=trading_day, prefer_trade_run=True)
    today_run = _latest_run(session, team_id, trading_day=trading_day, prefer_trade_run=True)
    selected_run = today_run or latest_run
    event_count = _event_count(session, selected_run.id) if selected_run is not None else 0
    event_ledger_ready = (
        _event_ledger_ready(session, selected_run.id, event_count) if selected_run is not None else False
    )
    scheduler_decision = _latest_scheduler_decision(session, team_id)
    review_id = _review_id(session, selected_run)
    legacy_future_runs = _legacy_manual_future_runs(session, team_id, trading_day)
    data_quality_warnings = (
        ["legacy_manual_future_runs_detected"] if legacy_future_runs else []
    )
    run_state = _run_state(today_run)
    blockers = _blockers(
        run_state=run_state,
        run=today_run,
        review_id=review_id,
        event_ledger_ready=event_ledger_ready,
    )
    action = _recommended_action(run_state, blockers)
    health_status = _health_status(run_state, blockers)
    return PaperOperationsStatusPayload(
        trading_day=trading_day,
        run_state=run_state,
        health_status=health_status,
        latest_run_id=latest_run.id if latest_run is not None else None,
        latest_run_trading_day=latest_run.trading_day if latest_run is not None else None,
        latest_run_status=latest_run.status.value if latest_run is not None else None,
        today_run_id=today_run.id if today_run is not None else None,
        review_id=review_id,
        latest_error=selected_run.error_message if selected_run is not None else None,
        can_retry_today=run_state in {"not_started", "failed"},
        event_ledger_ready=event_ledger_ready,
        latest_run_event_count=event_count,
        legacy_manual_future_run_count=len(legacy_future_runs),
        latest_legacy_manual_future_trading_day=legacy_future_runs[0].trading_day if legacy_future_runs else None,
        data_quality_warnings=data_quality_warnings,
        latest_scheduler_decision=scheduler_decision["decision"],
        latest_scheduler_decision_at=scheduler_decision["published_at"],
        latest_scheduler_decision_trading_day=scheduler_decision["trading_day"],
        latest_scheduler_decision_reason=scheduler_decision["reason"],
        latest_scheduler_decision_summary=scheduler_decision["summary"],
        blockers=blockers,
        recommended_action=action,
        summary=_summary(run_state, health_status, action, blockers, data_quality_warnings),
    )


def quarantine_legacy_manual_future_runs(
    session: Session,
    *,
    team_id: UUID | None = None,
    trading_day: str | None = None,
    limit: int = 100,
) -> PaperOperationsQuarantinePayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    trading_day = trading_day or _current_trading_day()
    bounded_limit = max(1, min(limit, 500))
    runs = _legacy_manual_future_runs(session, team_id, trading_day)[:bounded_limit]
    items: list[PaperOperationsQuarantineItem] = []
    quarantined_runs = 0

    for run in runs:
        previous_trigger = run.trigger.value
        run.trigger = PaperRunTrigger.simulation
        session.add(run)
        session.add(
            CoreEventLog(
                team_id=run.team_id,
                run_id=run.id,
                event_id=f"quarantine-{run.id}",
                topic="run_audit",
                sequence=_event_count(session, run.id) + 1,
                correlation_id=f"paper-run:{run.id}",
                causation_id=None,
                payload_json=json.dumps(
                    {
                        "event_type": "legacy_manual_future_run_quarantined",
                        "run_id": str(run.id),
                        "trading_day": run.trading_day,
                        "previous_trigger": previous_trigger,
                        "new_trigger": PaperRunTrigger.simulation.value,
                        "reason": "manual_future_dated_run_reclassified_as_simulation",
                    },
                    sort_keys=True,
                ),
            )
        )
        quarantined_runs += 1
        items.append(
            PaperOperationsQuarantineItem(
                run_id=run.id,
                trading_day=run.trading_day,
                status=run.status.value,
                previous_trigger=previous_trigger,
                new_trigger=PaperRunTrigger.simulation.value,
                audit_event_created=True,
                reason="manual_future_dated_run_reclassified_as_simulation",
            )
        )

    if quarantined_runs:
        session.commit()
    skipped_runs = len(items) - quarantined_runs
    return PaperOperationsQuarantinePayload(
        scanned_runs=len(runs),
        quarantined_runs=quarantined_runs,
        skipped_runs=skipped_runs,
        items=items,
        summary=_quarantine_summary(
            scanned_runs=len(runs),
            quarantined_runs=quarantined_runs,
            skipped_runs=skipped_runs,
        ),
    )


def repair_paper_operations_event_ledger(
    session: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 30,
) -> PaperOperationsRepairPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    bounded_limit = max(1, min(limit, 100))
    runs = session.exec(
        select(PaperRun)
        .where(PaperRun.team_id == team_id)
        .order_by(PaperRun.started_at.desc())
        .limit(bounded_limit)
    ).all()
    items: list[PaperOperationsRepairItem] = []
    repaired_runs = 0
    for run in runs:
        event_count = _event_count(session, run.id)
        if event_count > 0:
            reason = (
                "event_ledger_already_present"
                if _event_ledger_ready(session, run.id, event_count)
                else "event_ledger_integrity_failed"
            )
            items.append(_repair_item(run, event_created=False, topic=None, reason=reason))
            continue
        if run.status not in {PaperRunStatus.completed, PaperRunStatus.skipped}:
            items.append(_repair_item(run, event_created=False, topic=None, reason="status_not_repairable"))
            continue

        topic = "run_audit"
        session.add(
            CoreEventLog(
                team_id=run.team_id,
                run_id=run.id,
                event_id=f"repair-{run.id}",
                topic=topic,
                sequence=1,
                correlation_id=f"paper-run:{run.id}",
                causation_id=None,
                payload_json=json.dumps(
                    {
                        "event_type": "paper_run_ledger_repaired",
                        "run_id": str(run.id),
                        "trading_day": run.trading_day,
                        "status": run.status.value,
                        "reason": "historical_run_missing_runtime_events",
                    },
                    sort_keys=True,
                ),
            )
        )
        repaired_runs += 1
        items.append(_repair_item(run, event_created=True, topic=topic, reason="audit_event_created"))

    if repaired_runs:
        session.commit()
    skipped_runs = len(items) - repaired_runs
    return PaperOperationsRepairPayload(
        scanned_runs=len(runs),
        repaired_runs=repaired_runs,
        skipped_runs=skipped_runs,
        items=items,
        summary=_repair_summary(scanned_runs=len(runs), repaired_runs=repaired_runs, skipped_runs=skipped_runs),
    )


def get_paper_operations_history(
    session: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 5,
) -> PaperOperationsHistoryPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    bounded_limit = max(1, min(limit, 30))
    as_of_trading_day = _current_trading_day()
    runs = session.exec(
        select(PaperRun)
        .where(PaperRun.team_id == team_id)
        .where(PaperRun.trading_day <= as_of_trading_day)
        .order_by(PaperRun.started_at.desc())
        .limit(bounded_limit)
    ).all()
    items: list[PaperOperationsHistoryItem] = []
    for run in runs:
        event_count = _event_count(session, run.id)
        event_ledger_ready = _event_ledger_ready(session, run.id, event_count)
        review_id = _review_id(session, run)
        run_state = _run_state(run)
        blockers = _blockers(
            run_state=run_state,
            run=run,
            review_id=review_id,
            event_ledger_ready=event_ledger_ready,
        )
        items.append(
            PaperOperationsHistoryItem(
                trading_day=run.trading_day,
                run_id=run.id,
                status=run.status.value,
                health_status=_health_status(run_state, blockers),
                event_count=event_count,
                has_review=review_id is not None,
                candidates_count=run.candidates_count,
                orders_count=run.orders_count,
                positions_count=run.positions_count,
                blockers=blockers,
                error_message=run.error_message,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
        )

    window_size = len(items)
    completed_days = sum(
        1
        for item in items
        if item.health_status == "ready" and item.status in {PaperRunStatus.completed.value, PaperRunStatus.skipped.value}
    )
    failed_days = sum(1 for item in items if item.status == PaperRunStatus.failed.value)
    blocked_days = sum(1 for item in items if item.health_status == "blocked")
    replayable_days = sum(
        1
        for item in items
        if item.event_count > 0 and "event_ledger_not_replayable" not in item.blockers
    )
    review_days = sum(1 for item in items if item.has_review)
    completion_rate = _ratio(completed_days, window_size)
    replay_rate = _ratio(replayable_days, window_size)
    latest_health_status: PaperOperationsHealthStatus = items[0].health_status if items else "blocked"
    return PaperOperationsHistoryPayload(
        window_size=window_size,
        completed_days=completed_days,
        failed_days=failed_days,
        blocked_days=blocked_days,
        replayable_days=replayable_days,
        review_days=review_days,
        completion_rate=completion_rate,
        replay_rate=replay_rate,
        latest_health_status=latest_health_status,
        items=items,
        summary=_history_summary(window_size, completion_rate, replay_rate, blocked_days, failed_days),
    )


def _repair_item(
    run: PaperRun,
    *,
    event_created: bool,
    topic: str | None,
    reason: str,
) -> PaperOperationsRepairItem:
    return PaperOperationsRepairItem(
        run_id=run.id,
        trading_day=run.trading_day,
        status=run.status.value,
        event_created=event_created,
        topic=topic,
        reason=reason,
    )


def _latest_run(
    session: Session,
    team_id: UUID,
    *,
    trading_day: str | None = None,
    as_of_trading_day: str | None = None,
    prefer_trade_run: bool = False,
) -> PaperRun | None:
    query = select(PaperRun).where(PaperRun.team_id == team_id)
    if trading_day is not None:
        query = query.where(PaperRun.trading_day == trading_day)
    elif as_of_trading_day is not None:
        query = query.where(PaperRun.trading_day <= as_of_trading_day)
    runs = list(session.exec(query.order_by(PaperRun.started_at.desc())).all())
    if not runs or not prefer_trade_run:
        return runs[0] if runs else None
    latest = runs[0]
    if latest.status != PaperRunStatus.skipped or _has_trade_replay_events(session, latest.id):
        return latest
    for run in runs[1:]:
        if run.status == PaperRunStatus.completed and _has_trade_replay_events(session, run.id):
            return run
    return latest


def _has_trade_replay_events(session: Session, run_id: UUID) -> bool:
    events = session.exec(select(CoreEventLog.topic).where(CoreEventLog.run_id == run_id)).all()
    return bool(set(events) & {"market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"})


def _legacy_manual_future_runs(
    session: Session,
    team_id: UUID,
    trading_day: str,
) -> list[PaperRun]:
    return list(
        session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.trading_day > trading_day)
            .where(PaperRun.trigger == PaperRunTrigger.manual)
            .where(PaperRun.status.in_([PaperRunStatus.completed, PaperRunStatus.skipped]))
            .order_by(PaperRun.trading_day.desc(), PaperRun.started_at.desc())
        ).all()
    )


def _latest_scheduler_decision(session: Session, team_id: UUID) -> dict[str, datetime | str | None]:
    event = session.exec(
        select(CoreEventLog)
        .where(CoreEventLog.team_id == team_id)
        .where(CoreEventLog.run_id == None)  # noqa: E711
        .where(CoreEventLog.topic == "scheduler_decision")
        .order_by(CoreEventLog.sequence.desc(), CoreEventLog.published_at.desc())
    ).first()
    if event is None:
        return _empty_scheduler_decision()
    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError:
        return {
            **_empty_scheduler_decision(),
            "published_at": event.published_at,
            "summary": "Malformed scheduler_decision payload.",
        }
    if not isinstance(payload, dict):
        return {
            **_empty_scheduler_decision(),
            "published_at": event.published_at,
            "summary": "Malformed scheduler_decision payload.",
        }
    summary = _payload_string(payload, "summary")
    return {
        "decision": _scheduler_decision_outcome(payload, summary),
        "published_at": event.published_at,
        "trading_day": _payload_string(payload, "trading_day"),
        "reason": _payload_string(payload, "reason"),
        "summary": summary,
    }


def _empty_scheduler_decision() -> dict[str, datetime | str | None]:
    return {
        "decision": None,
        "published_at": None,
        "trading_day": None,
        "reason": None,
        "summary": None,
    }


def _scheduler_decision_outcome(payload: dict, summary: str | None) -> PaperSchedulerDecision:
    if payload.get("executed") is True:
        return "executed"
    if (summary or "").lower().startswith("scheduled paper trading failed"):
        return "failed"
    return "skipped"


def _payload_string(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _event_count(session: Session, run_id: UUID) -> int:
    return len(session.exec(select(CoreEventLog).where(CoreEventLog.run_id == run_id)).all())


def _event_ledger_ready(session: Session, run_id: UUID, event_count: int) -> bool:
    if event_count <= 0:
        return False
    replay = replay_paper_run(session, run_id)
    run = session.get(PaperRun, run_id)
    if run is not None and run.status == PaperRunStatus.skipped:
        return all(not chain.integrity_warnings for chain in replay.chains)
    complete_order_chains = [chain for chain in replay.chains if _is_complete_order_chain(chain.topics) and not chain.integrity_warnings]
    candidate_only_chains = [
        chain
        for chain in replay.chains
        if bool(set(chain.topics) & {"market_event", "strategy_input", "trade_intent"})
        and not bool(set(chain.topics) & {"risk_decision", "order_state"})
        and not chain.integrity_warnings
    ]
    broken_order_chains = [
        chain
        for chain in replay.chains
        if bool(set(chain.topics) & {"risk_decision", "order_state"})
        and not (_is_complete_order_chain(chain.topics) and not chain.integrity_warnings)
    ]
    if broken_order_chains:
        return False
    return bool(complete_order_chains or candidate_only_chains)


def _is_complete_order_chain(topics: list[str]) -> bool:
    return {"market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"}.issubset(set(topics))


def _review_id(session: Session, run: PaperRun | None) -> UUID | None:
    if run is None:
        return None
    if run.review_id is not None:
        return run.review_id
    review = session.exec(
        select(PaperReview).where(
            PaperReview.team_id == run.team_id,
            PaperReview.trading_day == run.trading_day,
        )
    ).first()
    return review.id if review is not None else None


def _run_state(run: PaperRun | None) -> PaperOperationsRunState:
    if run is None:
        return "not_started"
    if run.status == PaperRunStatus.started:
        return "running"
    return run.status.value


def _blockers(
    *,
    run_state: PaperOperationsRunState,
    run: PaperRun | None,
    review_id: UUID | None,
    event_ledger_ready: bool,
) -> list[str]:
    if run_state == "not_started":
        return ["daily_run_missing"]
    if run_state == "running":
        return ["running_run_stale"] if run is not None and _running_run_is_stale(run) else []
    if run_state == "failed":
        return ["latest_run_failed"]

    blockers: list[str] = []
    if run_state == "completed" and review_id is None:
        blockers.append("review_missing")
    if run is not None and not event_ledger_ready:
        blockers.append("event_ledger_not_replayable")
    return blockers


def _recommended_action(
    run_state: PaperOperationsRunState,
    blockers: list[str],
) -> PaperOperationsAction:
    if run_state == "not_started":
        return "run_daily_paper_trading"
    if run_state == "failed":
        return "retry_daily_paper_trading"
    if "running_run_stale" in blockers:
        return "retry_daily_paper_trading"
    if run_state == "running":
        return "wait_for_running_job"
    if "event_ledger_not_replayable" in blockers or "review_missing" in blockers:
        return "repair_event_ledger"
    return "hold_until_next_session"


def _health_status(
    run_state: PaperOperationsRunState,
    blockers: list[str],
) -> PaperOperationsHealthStatus:
    if run_state in {"not_started", "failed"} or blockers:
        return "blocked"
    if run_state == "running":
        return "warning"
    return "ready"


def _summary(
    run_state: PaperOperationsRunState,
    health_status: PaperOperationsHealthStatus,
    action: PaperOperationsAction,
    blockers: list[str],
    data_quality_warnings: list[str],
) -> str:
    if health_status == "ready":
        summary = "Daily paper pipeline is complete for the trading day; hold until the next session."
        if "legacy_manual_future_runs_detected" in data_quality_warnings:
            return f"{summary} Data quality warning: legacy manual future-dated runs detected."
        return summary
    if run_state == "running":
        summary = "Daily paper pipeline is currently running; wait for the job to finish."
    else:
        summary = f"Daily paper pipeline requires action {action}; blockers: {', '.join(blockers) or 'none'}."
    if "legacy_manual_future_runs_detected" in data_quality_warnings:
        return f"{summary} Data quality warning: legacy manual future-dated runs detected."
    return summary


def _running_run_is_stale(run: PaperRun) -> bool:
    started_at = run.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return started_at <= datetime.now(timezone.utc) - timedelta(minutes=RUNNING_LOCK_STALE_AFTER_MINUTES)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0
    return round(numerator / denominator, 4)


def _history_summary(
    window_size: int,
    completion_rate: float,
    replay_rate: float,
    blocked_days: int,
    failed_days: int,
) -> str:
    if window_size <= 0:
        return "No paper operations history is available yet."
    if blocked_days == 0 and failed_days == 0:
        return f"Last {window_size} paper runs are operationally healthy; completion {completion_rate:.0%}, replay {replay_rate:.0%}."
    return (
        f"Last {window_size} paper runs include {blocked_days} blocked and {failed_days} failed runs; "
        f"completion {completion_rate:.0%}, replay {replay_rate:.0%}."
    )


def _repair_summary(scanned_runs: int, repaired_runs: int, skipped_runs: int) -> str:
    if scanned_runs <= 0:
        return "No paper runs were available for event ledger repair."
    if repaired_runs <= 0:
        return f"Scanned {scanned_runs} paper runs; no missing repairable event ledgers were found."
    return f"Scanned {scanned_runs} paper runs; repaired {repaired_runs} missing event ledgers and skipped {skipped_runs}."


def _quarantine_summary(scanned_runs: int, quarantined_runs: int, skipped_runs: int) -> str:
    if scanned_runs <= 0:
        return "No legacy manual future-dated paper runs were found."
    return (
        f"Scanned {scanned_runs} legacy manual future-dated runs; "
        f"quarantined {quarantined_runs} as simulation and skipped {skipped_runs}."
    )


def _current_trading_day() -> str:
    return current_market_trading_day()
