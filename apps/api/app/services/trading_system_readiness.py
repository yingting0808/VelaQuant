from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.alpha_gate_progress import AlphaGateProgressPayload, get_alpha_gate_progress
from app.services.event_bus_health import EventBusHealthPayload, get_event_bus_health
from app.services.event_ledger import EventLedgerStatus, get_event_ledger_status
from app.services.live_small_review import LiveSmallReviewPayload, get_live_small_review_packet
from app.services.paper_scheduler import PaperSchedulerStatus, get_paper_scheduler_status
from app.services.shadow_observation import ShadowObservationSummaryPayload, get_shadow_observations
from app.services.shadow_validation import ShadowValidationPayload, get_shadow_validation
from app.services.strategy_alpha_isolation import StrategyAlphaIsolationPayload, get_strategy_alpha_isolation
from app.services.strategy_lifecycle import StrategyLifecyclePayload, get_strategy_lifecycle


TradingSystemReadinessStatus = Literal["operational", "attention", "blocked"]


class TradingSystemReadinessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TradingSystemReadinessStatus
    scheduler_running: bool
    scheduler_next_run_at: str | None
    lifecycle_stage: str
    alpha_ready: bool
    event_bus_mode: str
    event_bus_ready: bool
    event_bus_stream_length: int | None
    event_ledger_replay_ready: bool
    event_ledger_traceable_chain_count: int
    event_ledger_complete_order_chain_count: int
    event_ledger_broken_chain_count: int
    event_ledger_traceability_ratio: float
    shadow_can_record: bool
    shadow_remaining_observations: int
    live_small_review_ready: bool
    live_or_broker_execution_enabled: bool
    manual_override_isolated: bool
    manual_override_order_count: int
    manual_override_event_chain_count: int
    alpha_filtered_event_chain_count: int
    blockers: list[str]
    pending_gates: list[str]
    summary: str


def get_trading_system_readiness(session: Session) -> TradingSystemReadinessPayload:
    return build_trading_system_readiness(
        scheduler=get_paper_scheduler_status(),
        lifecycle=get_strategy_lifecycle(session),
        shadow_observations=get_shadow_observations(session),
        shadow_validation=get_shadow_validation(session),
        live_small_review=get_live_small_review_packet(session),
        event_ledger=get_event_ledger_status(session),
        event_bus=get_event_bus_health(),
        alpha_gates=get_alpha_gate_progress(session),
        alpha_isolation=get_strategy_alpha_isolation(session),
    )


def build_trading_system_readiness(
    *,
    scheduler: PaperSchedulerStatus,
    lifecycle: StrategyLifecyclePayload,
    shadow_observations: ShadowObservationSummaryPayload,
    shadow_validation: ShadowValidationPayload,
    live_small_review: LiveSmallReviewPayload,
    event_ledger: EventLedgerStatus,
    event_bus: EventBusHealthPayload,
    alpha_gates: AlphaGateProgressPayload,
    alpha_isolation: StrategyAlphaIsolationPayload,
) -> TradingSystemReadinessPayload:
    blockers: list[str] = []
    if not scheduler.running:
        blockers.append("scheduler_not_running")
    if not event_ledger.replay_ready:
        blockers.append("event_ledger_not_replayable")
    if event_ledger.broken_chain_count > 0:
        blockers.append("event_ledger_broken_trade_chains")
    if not event_bus.ready:
        blockers.append("event_bus_not_ready")
    if lifecycle.auto_actions_enabled:
        blockers.append("automatic_lifecycle_actions_enabled")
    if live_small_review.auto_promotion_enabled:
        blockers.append("automatic_live_small_promotion_enabled")
    if lifecycle.current_stage == "killed":
        blockers.append("strategy_killed")
    elif lifecycle.can_kill or lifecycle.recommended_stage == "killed":
        blockers.append("strategy_kill_review_required")
    if lifecycle.current_stage in {"shadow", "live_small", "live"} and not alpha_gates.alpha_ready:
        blockers.append("lifecycle_stage_ahead_of_alpha_validation")
    if not alpha_isolation.isolated:
        blockers.append("manual_override_alpha_leak")

    pending_gates: list[str] = []
    if not alpha_gates.alpha_ready:
        pending_gates.append("paper_alpha_validation")
    if lifecycle.current_stage != "shadow":
        pending_gates.append("shadow_stage")
    if not shadow_observations.can_record_shadow_observation:
        pending_gates.append("shadow_observation_recording")
    if not shadow_validation.shadow_ready:
        pending_gates.append("shadow_validation_sample")
    if not live_small_review.can_request_live_small_review:
        pending_gates.append("live_small_manual_review")

    if blockers:
        status: TradingSystemReadinessStatus = "blocked"
    elif pending_gates and not shadow_observations.can_record_shadow_observation:
        status = "attention"
    else:
        status = "operational"

    return TradingSystemReadinessPayload(
        status=status,
        scheduler_running=scheduler.running,
        scheduler_next_run_at=scheduler.next_run_at.isoformat() if scheduler.next_run_at is not None else None,
        lifecycle_stage=lifecycle.current_stage,
        alpha_ready=alpha_gates.alpha_ready,
        event_bus_mode=event_bus.mode,
        event_bus_ready=event_bus.ready,
        event_bus_stream_length=event_bus.stream_length,
        event_ledger_replay_ready=event_ledger.replay_ready,
        event_ledger_traceable_chain_count=event_ledger.traceable_chain_count,
        event_ledger_complete_order_chain_count=event_ledger.complete_order_chain_count,
        event_ledger_broken_chain_count=event_ledger.broken_chain_count,
        event_ledger_traceability_ratio=event_ledger.traceability_ratio,
        shadow_can_record=shadow_observations.can_record_shadow_observation,
        shadow_remaining_observations=shadow_validation.remaining_observations,
        live_small_review_ready=live_small_review.can_request_live_small_review,
        live_or_broker_execution_enabled=False,
        manual_override_isolated=alpha_isolation.isolated,
        manual_override_order_count=alpha_isolation.manual_override_order_count,
        manual_override_event_chain_count=alpha_isolation.manual_override_event_chain_count,
        alpha_filtered_event_chain_count=alpha_isolation.filtered_event_chain_count,
        blockers=blockers,
        pending_gates=pending_gates,
        summary=_summary(status, blockers, pending_gates),
    )


def _summary(
    status: TradingSystemReadinessStatus,
    blockers: list[str],
    pending_gates: list[str],
) -> str:
    if status == "blocked":
        return f"Trading system readiness is blocked by {', '.join(blockers)}."
    if pending_gates:
        return f"Trading system is operational for controlled daily runs; pending gates: {', '.join(pending_gates)}."
    return "Trading system is operational with no pending gates; live or broker execution remains disabled."
