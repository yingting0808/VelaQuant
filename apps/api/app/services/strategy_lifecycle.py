from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

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
]
LifecycleGateStatus = Literal["blocked", "watch", "eligible"]
LifecycleRuleSeverity = Literal["blocker", "warning", "info"]

MIN_FILLED_ORDERS_FOR_SHADOW = 30
MIN_CLOSED_TRADES_FOR_SHADOW = 10
MAX_DRAWDOWN_FOR_SHADOW = 0.15

STRATEGY_LIFECYCLE_MISSING_CAPABILITIES = [
    "lifecycle_state_persistence",
    "manual_promotion_approval",
    "shadow_account_adapter",
    "live_small_account_adapter",
    "kill_switch_audit_trail",
]


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
    return build_strategy_lifecycle(evaluate_current_paper_strategy(session))


def build_strategy_lifecycle(evaluation: StrategyEvaluationPayload) -> StrategyLifecyclePayload:
    rules = _lifecycle_rules(evaluation)
    event_ledger_rule = next(rule for rule in rules if rule.name == "event_ledger_populated")
    blockers = [rule for rule in rules if rule.severity == "blocker" and not rule.passed]

    if evaluation.readiness == StrategyEvaluationReadiness.negative_expectancy:
        recommended_stage: LifecycleStage = "killed"
        recommended_action: LifecycleAction = "kill_review"
        gate_status: LifecycleGateStatus = "blocked"
        can_promote = False
        can_kill = True
        summary = "Negative expectancy is in the evaluation window; route to manual kill review, no auto action."
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
        current_stage="paper",
        recommended_stage=recommended_stage,
        recommended_action=recommended_action,
        gate_status=gate_status,
        promotion_gate=evaluation.promotion_gate,
        can_promote=can_promote,
        can_kill=can_kill,
        auto_actions_enabled=False,
        rules=rules,
        missing_capabilities=STRATEGY_LIFECYCLE_MISSING_CAPABILITIES.copy(),
        summary=summary,
    )


def _lifecycle_rules(evaluation: StrategyEvaluationPayload) -> list[StrategyLifecycleRule]:
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
            actual=f"{evaluation.event_chain_count} events",
            required="> 0 events",
            message="Event ledger is populated.",
        ),
        _rule(
            name="closed_trade_sample",
            passed=evaluation.closed_trade_count >= MIN_CLOSED_TRADES_FOR_SHADOW,
            actual=f"{evaluation.closed_trade_count} closed trades",
            required=f">= {MIN_CLOSED_TRADES_FOR_SHADOW} closed trades",
            message="Closed trade sample is large enough to inspect exits.",
        ),
    ]


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
