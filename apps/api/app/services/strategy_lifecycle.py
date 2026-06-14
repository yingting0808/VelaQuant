from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import StrategyLifecycleState, utc_now
from app.services.alpha_validation import get_alpha_validation
from app.services.alpha_validation_snapshot import get_alpha_validation_snapshots
from app.services.strategy_evaluation import (
    StrategyEvaluationPayload,
    StrategyEvaluationReadiness,
    evaluate_current_paper_strategy,
)


LifecycleStage = Literal["paper", "shadow_candidate", "shadow", "live_small", "live", "killed"]
LifecycleAction = Literal[
    "continue_collecting_samples",
    "keep_paper_running",
    "eligible_for_shadow_review",
    "repair_event_ledger",
    "kill_review",
    "auto_promoted_to_shadow",
    "auto_promoted_to_live_small",
    "auto_promoted_to_live",
    "auto_killed_negative_expectancy",
    "hold_current_stage",
]
LifecycleGateStatus = Literal["blocked", "watch", "eligible"]
LifecycleRuleSeverity = Literal["blocker", "warning", "info"]

MIN_FILLED_ORDERS_FOR_SHADOW = 30
MIN_CLOSED_TRADES_FOR_SHADOW = 10
MAX_DRAWDOWN_FOR_SHADOW = 0.15

STRATEGY_LIFECYCLE_MISSING_CAPABILITIES: list[str] = []


class StrategyLifecycleRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    severity: LifecycleRuleSeverity
    actual: str
    required: str
    message: str


class StrategyLifecyclePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    strategy_name: str
    current_stage: LifecycleStage
    recommended_stage: LifecycleStage
    recommended_action: LifecycleAction
    gate_status: LifecycleGateStatus
    promotion_gate: str
    can_promote: bool
    can_kill: bool
    auto_actions_enabled: bool
    rules: list[StrategyLifecycleRule]
    missing_capabilities: list[str]
    summary: str


def get_strategy_lifecycle(session: Session) -> StrategyLifecyclePayload:
    return apply_strategy_lifecycle_state_machine(session, evaluate_current_paper_strategy(session))


def apply_strategy_lifecycle_state_machine(
    session: Session,
    evaluation: StrategyEvaluationPayload,
) -> StrategyLifecyclePayload:
    state = _get_or_create_lifecycle_state(session, evaluation.strategy_id)
    _quarantine_legacy_auto_state(session, state)
    alpha_validation = get_alpha_validation(session, strategy_id=evaluation.strategy_id)
    alpha_ready = alpha_validation.alpha_ready
    alpha_snapshots = get_alpha_validation_snapshots(session, strategy_id=evaluation.strategy_id)
    alpha_snapshot_ready = alpha_snapshots.latest is not None and alpha_snapshots.latest.alpha_ready

    return build_strategy_lifecycle(
        evaluation,
        current_stage=_coerce_lifecycle_stage(state.current_stage),
        auto_actions_enabled=False,
        alpha_ready=alpha_ready,
        alpha_snapshot_ready=alpha_snapshot_ready,
    )


def build_strategy_lifecycle(
    evaluation: StrategyEvaluationPayload,
    *,
    current_stage: LifecycleStage = "paper",
    auto_actions_enabled: bool = False,
    transition_action: LifecycleAction | None = None,
    transition_reason: str | None = None,
    alpha_ready: bool = True,
    alpha_snapshot_ready: bool = True,
) -> StrategyLifecyclePayload:
    rules = _lifecycle_rules(evaluation, alpha_ready=alpha_ready, alpha_snapshot_ready=alpha_snapshot_ready)
    event_ledger_rule = next(rule for rule in rules if rule.name == "event_ledger_populated")
    blockers = [rule for rule in rules if rule.severity == "blocker" and not rule.passed]

    if transition_action is not None:
        recommended_stage = current_stage
        recommended_action = transition_action
        gate_status = "blocked" if current_stage == "killed" else "eligible"
        can_promote = False
        can_kill = False
        summary = transition_reason or "Lifecycle state machine applied an automatic transition."
    elif current_stage == "killed":
        recommended_stage = "killed"
        recommended_action = "hold_current_stage"
        gate_status = "blocked"
        can_promote = False
        can_kill = False
        summary = "Strategy is killed; execution remains blocked."
    elif evaluation.readiness == StrategyEvaluationReadiness.negative_expectancy:
        recommended_stage: LifecycleStage = "killed"
        recommended_action: LifecycleAction = "kill_review"
        gate_status: LifecycleGateStatus = "blocked"
        can_promote = False
        can_kill = True
        summary = "Negative expectancy is in the evaluation window; route to manual kill review, no auto action."
    elif current_stage == "shadow":
        recommended_stage = "shadow"
        recommended_action = "hold_current_stage"
        gate_status = "watch"
        can_promote = False
        can_kill = False
        summary = "Strategy is in Shadow; collect Shadow observations and use the live-small review gate for the next manual decision."
    elif current_stage == "live_small":
        recommended_stage = "live_small"
        recommended_action = "hold_current_stage"
        gate_status = "watch"
        can_promote = False
        can_kill = False
        summary = "Strategy is in live-small review mode; broker execution remains disabled until a separate live approval exists."
    elif evaluation.readiness == StrategyEvaluationReadiness.paper_ready and not event_ledger_rule.passed:
        recommended_stage = "paper"
        recommended_action = "repair_event_ledger"
        gate_status = "blocked"
        can_promote = False
        can_kill = False
        summary = "Paper metrics are ready, but event ledger runtime is empty; repair audit trail before promotion."
    elif evaluation.readiness == StrategyEvaluationReadiness.paper_ready and not blockers:
        recommended_stage = "shadow_candidate"
        recommended_action = "eligible_for_shadow_review"
        gate_status = "eligible"
        can_promote = True
        can_kill = False
        summary = "Eligible for shadow_candidate manual review; automatic promotion remains disabled."
    elif evaluation.readiness == StrategyEvaluationReadiness.paper_ready and blockers:
        recommended_stage = "paper"
        recommended_action = "continue_collecting_samples"
        gate_status = "blocked"
        can_promote = False
        can_kill = False
        summary = "Paper metrics are ready, but alpha validation gates still need more evidence."
    elif evaluation.readiness == StrategyEvaluationReadiness.watch:
        recommended_stage = "paper"
        recommended_action = "keep_paper_running"
        gate_status = "watch"
        can_promote = False
        can_kill = False
        summary = "Positive expectancy is emerging, but paper-stage gates still need more evidence."
    else:
        recommended_stage = "paper"
        recommended_action = "continue_collecting_samples"
        gate_status = "watch"
        can_promote = False
        can_kill = False
        summary = "Insufficient paper evidence; continue collecting samples before any lifecycle transition."

    return StrategyLifecyclePayload(
        strategy_id=evaluation.strategy_id,
        strategy_name=evaluation.strategy_name,
        current_stage=current_stage,
        recommended_stage=recommended_stage,
        recommended_action=recommended_action,
        gate_status=gate_status,
        promotion_gate=evaluation.promotion_gate,
        can_promote=can_promote,
        can_kill=can_kill,
        auto_actions_enabled=auto_actions_enabled,
        rules=rules,
        missing_capabilities=STRATEGY_LIFECYCLE_MISSING_CAPABILITIES.copy(),
        summary=summary,
    )


def _lifecycle_rules(
    evaluation: StrategyEvaluationPayload,
    *,
    alpha_ready: bool,
    alpha_snapshot_ready: bool,
) -> list[StrategyLifecycleRule]:
    return [
        _rule(
            name="minimum_filled_orders",
            passed=evaluation.filled_order_count >= MIN_FILLED_ORDERS_FOR_SHADOW,
            actual=f"{evaluation.filled_order_count} filled orders",
            required=f">= {MIN_FILLED_ORDERS_FOR_SHADOW} filled orders",
            message="Filled order sample is large enough for shadow review.",
        ),
        _rule(
            name="positive_expectancy",
            passed=evaluation.expectancy > 0,
            actual=f"{evaluation.expectancy:.2f}",
            required="> 0.00 expectancy",
            message="Observed expectancy is positive.",
        ),
        _rule(
            name="drawdown_limit",
            passed=evaluation.max_drawdown <= MAX_DRAWDOWN_FOR_SHADOW,
            actual=f"{evaluation.max_drawdown:.2%}",
            required=f"<= {MAX_DRAWDOWN_FOR_SHADOW:.2%}",
            message="Observed max drawdown is inside the paper-to-shadow limit.",
        ),
        _rule(
            name="event_ledger_populated",
            passed=evaluation.event_chain_count > 0,
            actual=f"{evaluation.event_chain_count} chains",
            required="> 0 chains",
            message="Event ledger has replayable trade chains.",
        ),
        _rule(
            name="closed_trade_sample",
            passed=evaluation.closed_trade_count >= MIN_CLOSED_TRADES_FOR_SHADOW,
            actual=f"{evaluation.closed_trade_count} closed trades",
            required=f">= {MIN_CLOSED_TRADES_FOR_SHADOW} closed trades",
            message="Closed trade sample is large enough to inspect exits.",
        ),
        _rule(
            name="alpha_validation_ready",
            passed=alpha_ready,
            actual="ready" if alpha_ready else "not ready",
            required="paper alpha validation passed",
            message="Alpha validation confirms stable paper expectancy.",
        ),
        _rule(
            name="alpha_snapshot_history_ready",
            passed=alpha_snapshot_ready,
            actual="ready snapshot recorded" if alpha_snapshot_ready else "no ready snapshot",
            required="latest persisted alpha snapshot is ready",
            message="Alpha validation has been persisted into the daily snapshot ledger.",
        ),
    ]


def _eligible_for_shadow(
    evaluation: StrategyEvaluationPayload,
    *,
    alpha_ready: bool,
    alpha_snapshot_ready: bool,
) -> bool:
    return (
        evaluation.readiness == StrategyEvaluationReadiness.paper_ready
        and evaluation.filled_order_count >= MIN_FILLED_ORDERS_FOR_SHADOW
        and evaluation.closed_trade_count >= MIN_CLOSED_TRADES_FOR_SHADOW
        and evaluation.expectancy > 0
        and evaluation.max_drawdown <= MAX_DRAWDOWN_FOR_SHADOW
        and evaluation.event_chain_count > 0
        and alpha_ready
        and alpha_snapshot_ready
    )


def _get_or_create_lifecycle_state(session: Session, strategy_id: str) -> StrategyLifecycleState:
    state = session.exec(
        select(StrategyLifecycleState).where(StrategyLifecycleState.strategy_id == strategy_id)
    ).first()
    if state is not None:
        return state

    state = StrategyLifecycleState(strategy_id=strategy_id, current_stage="paper")
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def _quarantine_legacy_auto_state(session: Session, state: StrategyLifecycleState) -> None:
    if state.auto_transition_count <= 0 and "automatic" not in state.transition_reason.lower():
        return
    state.current_stage = "paper"
    state.transition_reason = "automatic lifecycle transitions disabled; reset to paper pending manual review."
    state.auto_transition_count = 0
    state.updated_at = utc_now()
    session.add(state)
    session.commit()
    session.refresh(state)


def _coerce_lifecycle_stage(value: str) -> LifecycleStage:
    if value in {"paper", "shadow_candidate", "shadow", "live_small", "live", "killed"}:
        return value  # type: ignore[return-value]
    return "paper"


def _rule(
    *,
    name: str,
    passed: bool,
    actual: str,
    required: str,
    message: str,
) -> StrategyLifecycleRule:
    return StrategyLifecycleRule(
        name=name,
        passed=passed,
        severity="blocker",
        actual=actual,
        required=required,
        message=message if passed else f"{message} Required: {required}; actual: {actual}.",
    )
