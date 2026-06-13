from app.services.strategy_evaluation import StrategyEvaluationPayload, StrategyEvaluationReadiness
from app.services.strategy_lifecycle import (
    STRATEGY_LIFECYCLE_MISSING_CAPABILITIES,
    build_strategy_lifecycle,
)


def test_strategy_lifecycle_marks_paper_ready_strategy_as_shadow_candidate():
    payload = build_strategy_lifecycle(
        _evaluation(
            readiness=StrategyEvaluationReadiness.paper_ready,
            filled_order_count=36,
            closed_trade_count=14,
            expectancy=6.4,
            max_drawdown=0.08,
            stability_score=0.84,
            event_chain_count=120,
            promotion_gate="eligible_for_shadow",
        )
    )

    assert payload.strategy_id == "deterministic_watchlist_v1"
    assert payload.current_stage == "paper"
    assert payload.recommended_stage == "shadow_candidate"
    assert payload.recommended_action == "eligible_for_shadow_review"
    assert payload.gate_status == "eligible"
    assert payload.can_promote is True
    assert payload.can_kill is False
    assert payload.auto_actions_enabled is False
    assert {rule.name for rule in payload.rules if rule.passed} >= {
        "minimum_filled_orders",
        "positive_expectancy",
        "drawdown_limit",
        "event_ledger_populated",
        "closed_trade_sample",
    }
    assert payload.missing_capabilities == STRATEGY_LIFECYCLE_MISSING_CAPABILITIES
    assert "manual review" in payload.summary


def test_strategy_lifecycle_blocks_shadow_without_event_ledger_runtime():
    payload = build_strategy_lifecycle(
        _evaluation(
            readiness=StrategyEvaluationReadiness.paper_ready,
            filled_order_count=36,
            closed_trade_count=14,
            expectancy=6.4,
            max_drawdown=0.08,
            stability_score=0.84,
            event_chain_count=0,
            promotion_gate="eligible_for_shadow",
        )
    )

    ledger_rule = next(rule for rule in payload.rules if rule.name == "event_ledger_populated")
    assert payload.current_stage == "paper"
    assert payload.recommended_stage == "paper"
    assert payload.recommended_action == "repair_event_ledger"
    assert payload.gate_status == "blocked"
    assert payload.can_promote is False
    assert ledger_rule.passed is False
    assert ledger_rule.severity == "blocker"
    assert ledger_rule.actual == "0 events"


def test_strategy_lifecycle_flags_negative_expectancy_for_kill_review():
    payload = build_strategy_lifecycle(
        _evaluation(
            readiness=StrategyEvaluationReadiness.negative_expectancy,
            filled_order_count=24,
            closed_trade_count=8,
            expectancy=-3.2,
            max_drawdown=0.06,
            stability_score=0.31,
            event_chain_count=70,
            promotion_gate="blocked",
        )
    )

    assert payload.current_stage == "paper"
    assert payload.recommended_stage == "killed"
    assert payload.recommended_action == "kill_review"
    assert payload.gate_status == "blocked"
    assert payload.can_promote is False
    assert payload.can_kill is True
    assert payload.auto_actions_enabled is False


def _evaluation(
    *,
    readiness: StrategyEvaluationReadiness,
    filled_order_count: int,
    closed_trade_count: int,
    expectancy: float,
    max_drawdown: float,
    stability_score: float,
    event_chain_count: int,
    promotion_gate: str,
) -> StrategyEvaluationPayload:
    return StrategyEvaluationPayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        sample_size=filled_order_count + 2,
        filled_order_count=filled_order_count,
        rejected_order_count=1,
        closed_trade_count=closed_trade_count,
        signal_precision=0.72,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
        stability_score=stability_score,
        readiness=readiness,
        promotion_gate=promotion_gate,
        event_chain_count=event_chain_count,
        notes="fixture",
    )
