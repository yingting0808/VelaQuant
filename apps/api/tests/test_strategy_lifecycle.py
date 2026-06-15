from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperReview,
    PaperRun,
    StrategyLifecycleState,
)
from app.services.strategy_evaluation import StrategyEvaluationPayload, StrategyEvaluationReadiness
from app.services.alpha_validation import AlphaValidationPayload
from app.services.alpha_validation_snapshot import record_alpha_validation_snapshot_from_payload
from app.services.strategy_lifecycle import (
    STRATEGY_LIFECYCLE_MISSING_CAPABILITIES,
    apply_strategy_lifecycle_state_machine,
    build_strategy_lifecycle,
)
from app.services.workspace import get_or_create_default_workspace


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
    assert "shadow_account_adapter" not in payload.missing_capabilities
    assert "live_small_account_adapter" not in payload.missing_capabilities
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
    assert ledger_rule.actual == "0 chains"


def test_lifecycle_blocks_promotion_when_alpha_validation_is_not_ready():
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
        ),
        alpha_ready=False,
    )

    alpha_rule = next(rule for rule in payload.rules if rule.name == "alpha_validation_ready")
    assert payload.current_stage == "paper"
    assert payload.recommended_stage == "paper"
    assert payload.recommended_action == "continue_collecting_samples"
    assert payload.gate_status == "blocked"
    assert payload.can_promote is False
    assert alpha_rule.passed is False


def test_lifecycle_blocks_promotion_when_alpha_snapshot_history_is_not_ready():
    with make_session() as session:
        _seed_alpha_ready_validation(session)

        payload = apply_strategy_lifecycle_state_machine(
            session,
            _evaluation(
                readiness=StrategyEvaluationReadiness.paper_ready,
                filled_order_count=36,
                closed_trade_count=14,
                expectancy=6.4,
                max_drawdown=0.08,
                stability_score=0.84,
                event_chain_count=120,
                promotion_gate="eligible_for_shadow",
            ),
        )

        snapshot_rule = next(rule for rule in payload.rules if rule.name == "alpha_snapshot_history_ready")
        assert payload.recommended_stage == "paper"
        assert payload.recommended_action == "continue_collecting_samples"
        assert payload.can_promote is False
        assert snapshot_rule.passed is False


def test_strategy_lifecycle_holds_after_manual_shadow_approval():
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
        ),
        current_stage="shadow",
    )

    assert payload.current_stage == "shadow"
    assert payload.recommended_stage == "shadow"
    assert payload.recommended_action == "hold_current_stage"
    assert payload.can_promote is False
    assert payload.auto_actions_enabled is False
    assert "Shadow" in payload.summary


def test_strategy_lifecycle_holds_after_manual_live_small_approval():
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
        ),
        current_stage="live_small",
    )

    assert payload.current_stage == "live_small"
    assert payload.recommended_stage == "live_small"
    assert payload.recommended_action == "hold_current_stage"
    assert payload.can_promote is False
    assert payload.auto_actions_enabled is False
    assert "live-small" in payload.summary


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


def test_lifecycle_state_machine_does_not_auto_promote_shadow(monkeypatch):
    with make_session() as session:
        monkeypatch.setattr("app.services.alpha_validation._has_real_market_backtest", lambda strategy_id: True)
        _seed_alpha_ready_validation(session)
        _seed_ready_alpha_snapshot(session)

        payload = apply_strategy_lifecycle_state_machine(
            session,
            _evaluation(
                readiness=StrategyEvaluationReadiness.paper_ready,
                filled_order_count=36,
                closed_trade_count=14,
                expectancy=6.4,
                max_drawdown=0.08,
                stability_score=0.84,
                event_chain_count=120,
                promotion_gate="eligible_for_shadow",
            ),
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        assert state.strategy_id == "deterministic_watchlist_v1"
        assert state.current_stage == "paper"
        assert state.auto_transition_count == 0
        assert payload.current_stage == "paper"
        assert payload.auto_actions_enabled is False
        assert payload.recommended_stage == "shadow_candidate"
        assert payload.recommended_action == "eligible_for_shadow_review"


def test_lifecycle_state_machine_does_not_auto_kill():
    with make_session() as session:
        payload = apply_strategy_lifecycle_state_machine(
            session,
            _evaluation(
                readiness=StrategyEvaluationReadiness.negative_expectancy,
                filled_order_count=36,
                closed_trade_count=14,
                expectancy=-2.1,
                max_drawdown=0.04,
                stability_score=0.2,
                event_chain_count=120,
                promotion_gate="blocked",
            ),
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        assert state.current_stage == "paper"
        assert state.auto_transition_count == 0
        assert payload.current_stage == "paper"
        assert payload.can_kill is True
        assert payload.auto_actions_enabled is False
        assert payload.recommended_action == "kill_review"


def test_lifecycle_state_machine_quarantines_legacy_auto_stage(monkeypatch):
    with make_session() as session:
        monkeypatch.setattr("app.services.alpha_validation._has_real_market_backtest", lambda strategy_id: True)
        session.add(
            StrategyLifecycleState(
                strategy_id="deterministic_watchlist_v1",
                current_stage="live",
                transition_reason="live_small->live automatic promotion: stability gate passed.",
                auto_transition_count=3,
            )
        )
        session.commit()
        _seed_alpha_ready_validation(session)
        _seed_ready_alpha_snapshot(session)

        payload = apply_strategy_lifecycle_state_machine(
            session,
            _evaluation(
                readiness=StrategyEvaluationReadiness.paper_ready,
                filled_order_count=36,
                closed_trade_count=14,
                expectancy=6.4,
                max_drawdown=0.08,
                stability_score=0.84,
                event_chain_count=120,
                promotion_gate="eligible_for_shadow",
            ),
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        assert state.current_stage == "paper"
        assert state.auto_transition_count == 0
        assert "disabled" in state.transition_reason
        assert payload.current_stage == "paper"
        assert payload.recommended_stage == "shadow_candidate"


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


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_alpha_ready_validation(session: Session) -> None:
    workspace = get_or_create_default_workspace(session)
    account = PaperAccount(team_id=workspace.team.id, name="paper")
    session.add(account)
    session.commit()
    session.refresh(account)

    for index in range(5):
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=workspace.team.id,
                trading_day=f"2026-06-0{index + 1}",
                equity=100000 + index * 100,
                cash=90000,
                realized_pnl=index * 10,
                unrealized_pnl=index * 20,
                trade_count=index + 1,
                win_rate=0.6,
                average_win=20,
                average_loss=-10,
                expectancy=1.0,
                notes="fixture",
            )
        )
    run = PaperRun(
        account_id=account.id,
        team_id=workspace.team.id,
        trading_day="2026-06-05",
        candidates_count=34,
        orders_count=34,
        positions_count=1,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    for index in range(34):
        submitted_at = datetime(2026, 6, (index % 5) + 1, tzinfo=timezone.utc)
        correlation_id = str(uuid4())
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=workspace.team.id,
                strategy_id="deterministic_watchlist_v1",
                ticker="AAPL",
                side=PaperOrderSide.sell if index < 12 else PaperOrderSide.buy,
                quantity=1,
                status=PaperOrderStatus.filled,
                fill_price=100,
                realized_pnl=1 if index < 12 else 0,
                submitted_at=submitted_at,
                filled_at=submitted_at,
            )
        )
        session.add(
            CoreEventLog(
                team_id=workspace.team.id,
                event_id=f"intent-{index}",
                topic="trade_intent",
                sequence=(index * 2) + 1,
                correlation_id=correlation_id,
                run_id=run.id,
                payload_json='{"strategy_id":"deterministic_watchlist_v1"}',
            )
        )
        session.add(
            CoreEventLog(
                team_id=workspace.team.id,
                event_id=f"order-{index}",
                topic="order_state",
                sequence=(index * 2) + 2,
                correlation_id=correlation_id,
                run_id=run.id,
                payload_json='{"order_strategy_id":"deterministic_watchlist_v1"}',
            )
        )
    session.commit()


def _seed_ready_alpha_snapshot(session: Session) -> None:
    workspace = get_or_create_default_workspace(session)
    record_alpha_validation_snapshot_from_payload(
        session,
        team_id=workspace.team.id,
        trading_day="2026-06-05",
        alpha=AlphaValidationPayload(
            strategy_id="deterministic_watchlist_v1",
            alpha_ready=True,
            validation_level="paper_validated",
            blockers=[],
            has_real_market_backtest=True,
            review_day_count=5,
            consecutive_positive_expectancy_days=5,
            filled_order_count=34,
            closed_trade_count=12,
            event_chain_count=34,
            latest_expectancy=1.0,
            average_expectancy=1.0,
            max_drawdown=0.01,
            summary="fixture",
        ),
    )
