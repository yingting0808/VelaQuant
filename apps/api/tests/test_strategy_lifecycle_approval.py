import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import AuditLog, StrategyLifecycleState
from app.services.live_small_review import LiveSmallReviewChecklistItem, LiveSmallReviewPayload
from app.services.shadow_review import ShadowReviewChecklistItem, ShadowReviewPayload
from app.services.strategy_lifecycle import StrategyLifecyclePayload, StrategyLifecycleRule
from app.services.strategy_lifecycle_approval import (
    approve_live_small_promotion_from_packet,
    approve_shadow_promotion_from_packet,
    approve_strategy_kill_from_lifecycle,
    reconcile_lifecycle_with_alpha_validation_from_lifecycle,
)


def test_manual_shadow_approval_promotes_stage_and_writes_audit_log():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="paper"))
        session.commit()

        result = approve_shadow_promotion_from_packet(
            session,
            shadow_review=ready_packet(),
            approved_by="operator",
            reason="Paper gates reviewed.",
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        audit = session.exec(select(AuditLog)).one()
        assert result.previous_stage == "paper"
        assert result.current_stage == "shadow"
        assert result.auto_promotion_enabled is False
        assert state.current_stage == "shadow"
        assert state.auto_transition_count == 0
        assert "manual shadow approval" in state.transition_reason
        assert audit.action == "strategy_shadow_approved"
        assert audit.entity_id == "deterministic_watchlist_v1"


def test_manual_shadow_approval_rejects_blocked_review_packet():
    with make_session() as session:
        blocked = ready_packet().model_copy(update={"status": "blocked", "can_request_shadow_review": False})

        with pytest.raises(ValueError, match="not ready for shadow approval"):
            approve_shadow_promotion_from_packet(
                session,
                shadow_review=blocked,
                approved_by="operator",
                reason="Too early.",
            )


def test_manual_live_small_approval_promotes_stage_and_writes_audit_log():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="shadow"))
        session.commit()

        result = approve_live_small_promotion_from_packet(
            session,
            live_small_review=ready_live_small_packet(),
            approved_by="operator",
            reason="Shadow sample reviewed.",
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        audit = session.exec(select(AuditLog).where(AuditLog.action == "strategy_live_small_approved")).one()
        assert result.previous_stage == "shadow"
        assert result.current_stage == "live_small"
        assert result.auto_promotion_enabled is False
        assert state.current_stage == "live_small"
        assert state.auto_transition_count == 0
        assert "manual live-small approval" in state.transition_reason
        assert audit.entity_id == "deterministic_watchlist_v1"


def test_manual_live_small_approval_rejects_when_current_stage_is_not_shadow():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="paper"))
        session.commit()

        with pytest.raises(ValueError, match="requires current lifecycle stage shadow"):
            approve_live_small_promotion_from_packet(
                session,
                live_small_review=ready_live_small_packet(),
                approved_by="operator",
                reason="Too early.",
            )


def test_manual_live_small_approval_rejects_blocked_review_packet():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="shadow"))
        session.commit()
        blocked = ready_live_small_packet().model_copy(
            update={"status": "blocked", "can_request_live_small_review": False}
        )

        with pytest.raises(ValueError, match="not ready for live-small approval"):
            approve_live_small_promotion_from_packet(
                session,
                live_small_review=blocked,
                approved_by="operator",
                reason="Too early.",
            )


def test_manual_strategy_kill_moves_stage_to_killed_and_writes_audit_log():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="shadow"))
        session.commit()

        result = approve_strategy_kill_from_lifecycle(
            session,
            lifecycle=kill_review_lifecycle_payload(),
            approved_by="operator",
            reason="Negative expectancy reviewed.",
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        audit = session.exec(select(AuditLog).where(AuditLog.action == "strategy_killed")).one()
        assert result.previous_stage == "shadow"
        assert result.current_stage == "killed"
        assert result.auto_promotion_enabled is False
        assert result.execution_enabled is False
        assert state.current_stage == "killed"
        assert state.auto_transition_count == 0
        assert "manual kill approval" in state.transition_reason
        assert audit.entity_id == "deterministic_watchlist_v1"


def test_manual_strategy_kill_rejects_lifecycle_without_kill_review():
    with make_session() as session:
        lifecycle = kill_review_lifecycle_payload().model_copy(
            update={
                "recommended_stage": "paper",
                "recommended_action": "keep_paper_running",
                "can_kill": False,
            }
        )

        with pytest.raises(ValueError, match="not ready for kill approval"):
            approve_strategy_kill_from_lifecycle(
                session,
                lifecycle=lifecycle,
                approved_by="operator",
                reason="Too early.",
            )


def test_lifecycle_reconcile_demotes_shadow_when_alpha_validation_is_not_ready():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="shadow"))
        session.commit()

        result = reconcile_lifecycle_with_alpha_validation_from_lifecycle(
            session,
            lifecycle=ahead_of_alpha_lifecycle_payload(current_stage="shadow", alpha_ready=False),
            reconciled_by="system_reconcile",
            reason="Alpha validation is not ready.",
        )

        state = session.exec(select(StrategyLifecycleState)).one()
        audit = session.exec(select(AuditLog).where(AuditLog.action == "strategy_lifecycle_reconciled")).one()
        assert result.reconciled is True
        assert result.previous_stage == "shadow"
        assert result.current_stage == "paper"
        assert result.alpha_ready is False
        assert result.auto_promotion_enabled is False
        assert result.execution_enabled is False
        assert state.current_stage == "paper"
        assert state.auto_transition_count == 0
        assert "alpha validation is not ready" in state.transition_reason.lower()
        assert audit.entity_id == "deterministic_watchlist_v1"


def test_lifecycle_reconcile_is_noop_when_stage_is_not_ahead_of_alpha_validation():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="paper"))
        session.commit()

        result = reconcile_lifecycle_with_alpha_validation_from_lifecycle(
            session,
            lifecycle=ahead_of_alpha_lifecycle_payload(current_stage="paper", alpha_ready=False),
            reconciled_by="system_reconcile",
            reason="Alpha validation is not ready.",
        )

        audits = session.exec(select(AuditLog)).all()
        assert result.reconciled is False
        assert result.previous_stage == "paper"
        assert result.current_stage == "paper"
        assert result.execution_enabled is False
        assert audits == []


def ready_packet() -> ShadowReviewPayload:
    return ShadowReviewPayload(
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
        residual_risks=[],
        summary="ready",
    )


def ready_live_small_packet() -> LiveSmallReviewPayload:
    return LiveSmallReviewPayload(
        status="ready_for_manual_review",
        strategy_id="deterministic_watchlist_v1",
        can_request_live_small_review=True,
        recommended_stage="live_small",
        auto_promotion_enabled=False,
        checklist=[
            LiveSmallReviewChecklistItem(
                code="shadow_health_stable",
                label="Shadow 健康稳定",
                passed=True,
                evidence=["stable"],
            )
        ],
        residual_risks=[],
        summary="ready",
    )


def kill_review_lifecycle_payload() -> StrategyLifecyclePayload:
    return StrategyLifecyclePayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        current_stage="shadow",
        recommended_stage="killed",
        recommended_action="kill_review",
        gate_status="blocked",
        promotion_gate="negative_expectancy",
        can_promote=False,
        can_kill=True,
        auto_actions_enabled=False,
        rules=[
            StrategyLifecycleRule(
                name="expectancy_positive",
                passed=False,
                severity="blocker",
                actual="-12.00",
                required="> 0",
                message="Expectancy is negative.",
            )
        ],
        missing_capabilities=[],
        summary="Strategy requires manual kill review.",
    )


def ahead_of_alpha_lifecycle_payload(*, current_stage: str, alpha_ready: bool) -> StrategyLifecyclePayload:
    return StrategyLifecyclePayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        current_stage=current_stage,
        recommended_stage=current_stage,
        recommended_action="hold_current_stage",
        gate_status="watch",
        promotion_gate="keep_paper_running",
        can_promote=False,
        can_kill=False,
        auto_actions_enabled=False,
        rules=[
            StrategyLifecycleRule(
                name="alpha_validation_ready",
                passed=alpha_ready,
                severity="blocker",
                actual="ready" if alpha_ready else "not ready",
                required="paper alpha validation passed",
                message="Alpha validation confirms stable paper expectancy.",
            )
        ],
        missing_capabilities=[],
        summary="Lifecycle fixture.",
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
