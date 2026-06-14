import json

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.domain.models import AuditLog, StrategyLifecycleState, utc_now
from app.services.live_small_review import LiveSmallReviewPayload, get_live_small_review_packet
from app.services.shadow_review import ShadowReviewPayload, get_shadow_review_packet
from app.services.strategy_lifecycle import StrategyLifecyclePayload, get_strategy_lifecycle


class StrategyShadowApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str = Field(default="manual_review", min_length=1)
    reason: str = Field(default="Shadow review approved manually.", min_length=1)


class StrategyShadowApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    previous_stage: str
    current_stage: str
    approved_by: str
    reason: str
    auto_promotion_enabled: bool
    summary: str


class StrategyLiveSmallApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str = Field(default="manual_review", min_length=1)
    reason: str = Field(default="Live-small review approved manually.", min_length=1)


class StrategyLiveSmallApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    previous_stage: str
    current_stage: str
    approved_by: str
    reason: str
    auto_promotion_enabled: bool
    live_or_broker_execution_enabled: bool
    summary: str


class StrategyKillApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str = Field(default="manual_review", min_length=1)
    reason: str = Field(default="Strategy kill reviewed manually.", min_length=1)


class StrategyKillApprovalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    previous_stage: str
    current_stage: str
    approved_by: str
    reason: str
    auto_promotion_enabled: bool
    execution_enabled: bool
    summary: str


class StrategyLifecycleReconcilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    previous_stage: str
    current_stage: str
    reconciled: bool
    reconciled_by: str
    reason: str
    alpha_ready: bool
    auto_promotion_enabled: bool
    execution_enabled: bool
    summary: str


def approve_shadow_promotion(
    session: Session,
    request: StrategyShadowApprovalRequest,
) -> StrategyShadowApprovalPayload:
    return approve_shadow_promotion_from_packet(
        session,
        shadow_review=get_shadow_review_packet(session),
        approved_by=request.approved_by,
        reason=request.reason,
    )


def approve_shadow_promotion_from_packet(
    session: Session,
    *,
    shadow_review: ShadowReviewPayload,
    approved_by: str,
    reason: str,
) -> StrategyShadowApprovalPayload:
    if not shadow_review.can_request_shadow_review or shadow_review.status != "ready_for_manual_review":
        raise ValueError(f"Strategy {shadow_review.strategy_id} is not ready for shadow approval.")

    state = _get_or_create_state(session, shadow_review.strategy_id)
    previous_stage = state.current_stage
    state.current_stage = "shadow"
    state.transition_reason = f"manual shadow approval by {approved_by}: {reason}"
    state.auto_transition_count = 0
    state.updated_at = utc_now()
    session.add(state)
    session.add(
        AuditLog(
            action="strategy_shadow_approved",
            entity_type="strategy",
            entity_id=shadow_review.strategy_id,
            metadata_json=json.dumps(
                {
                    "approved_by": approved_by,
                    "reason": reason,
                    "previous_stage": previous_stage,
                    "current_stage": "shadow",
                    "auto_promotion_enabled": False,
                },
                ensure_ascii=True,
            ),
        )
    )
    session.commit()
    session.refresh(state)
    return StrategyShadowApprovalPayload(
        strategy_id=shadow_review.strategy_id,
        previous_stage=previous_stage,
        current_stage=state.current_stage,
        approved_by=approved_by,
        reason=reason,
        auto_promotion_enabled=False,
        summary=f"Strategy {shadow_review.strategy_id} manually approved for shadow; automatic promotion remains disabled.",
    )


def approve_live_small_promotion(
    session: Session,
    request: StrategyLiveSmallApprovalRequest,
) -> StrategyLiveSmallApprovalPayload:
    return approve_live_small_promotion_from_packet(
        session,
        live_small_review=get_live_small_review_packet(session),
        approved_by=request.approved_by,
        reason=request.reason,
    )


def approve_live_small_promotion_from_packet(
    session: Session,
    *,
    live_small_review: LiveSmallReviewPayload,
    approved_by: str,
    reason: str,
) -> StrategyLiveSmallApprovalPayload:
    if (
        not live_small_review.can_request_live_small_review
        or live_small_review.status != "ready_for_manual_review"
    ):
        raise ValueError(f"Strategy {live_small_review.strategy_id} is not ready for live-small approval.")

    state = _get_or_create_state(session, live_small_review.strategy_id)
    previous_stage = state.current_stage
    if previous_stage != "shadow":
        raise ValueError("Live-small approval requires current lifecycle stage shadow.")

    state.current_stage = "live_small"
    state.transition_reason = f"manual live-small approval by {approved_by}: {reason}"
    state.auto_transition_count = 0
    state.updated_at = utc_now()
    session.add(state)
    session.add(
        AuditLog(
            action="strategy_live_small_approved",
            entity_type="strategy",
            entity_id=live_small_review.strategy_id,
            metadata_json=json.dumps(
                {
                    "approved_by": approved_by,
                    "reason": reason,
                    "previous_stage": previous_stage,
                    "current_stage": "live_small",
                    "auto_promotion_enabled": False,
                    "live_or_broker_execution_enabled": False,
                },
                ensure_ascii=True,
            ),
        )
    )
    session.commit()
    session.refresh(state)
    return StrategyLiveSmallApprovalPayload(
        strategy_id=live_small_review.strategy_id,
        previous_stage=previous_stage,
        current_stage=state.current_stage,
        approved_by=approved_by,
        reason=reason,
        auto_promotion_enabled=False,
        live_or_broker_execution_enabled=False,
        summary=(
            f"Strategy {live_small_review.strategy_id} manually approved for live-small review mode; "
            "broker execution remains disabled."
        ),
    )


def approve_strategy_kill(
    session: Session,
    request: StrategyKillApprovalRequest,
) -> StrategyKillApprovalPayload:
    return approve_strategy_kill_from_lifecycle(
        session,
        lifecycle=get_strategy_lifecycle(session),
        approved_by=request.approved_by,
        reason=request.reason,
    )


def approve_strategy_kill_from_lifecycle(
    session: Session,
    *,
    lifecycle: StrategyLifecyclePayload,
    approved_by: str,
    reason: str,
) -> StrategyKillApprovalPayload:
    if (
        not lifecycle.can_kill
        or lifecycle.recommended_stage != "killed"
        or lifecycle.recommended_action != "kill_review"
    ):
        raise ValueError(f"Strategy {lifecycle.strategy_id} is not ready for kill approval.")

    state = _get_or_create_state(session, lifecycle.strategy_id)
    previous_stage = state.current_stage
    state.current_stage = "killed"
    state.transition_reason = f"manual kill approval by {approved_by}: {reason}"
    state.auto_transition_count = 0
    state.updated_at = utc_now()
    session.add(state)
    session.add(
        AuditLog(
            action="strategy_killed",
            entity_type="strategy",
            entity_id=lifecycle.strategy_id,
            metadata_json=json.dumps(
                {
                    "approved_by": approved_by,
                    "reason": reason,
                    "previous_stage": previous_stage,
                    "current_stage": "killed",
                    "auto_promotion_enabled": False,
                    "execution_enabled": False,
                },
                ensure_ascii=True,
            ),
        )
    )
    session.commit()
    session.refresh(state)
    return StrategyKillApprovalPayload(
        strategy_id=lifecycle.strategy_id,
        previous_stage=previous_stage,
        current_stage=state.current_stage,
        approved_by=approved_by,
        reason=reason,
        auto_promotion_enabled=False,
        execution_enabled=False,
        summary=f"Strategy {lifecycle.strategy_id} manually killed; all execution remains disabled.",
    )


def reconcile_lifecycle_with_alpha_validation(session: Session) -> StrategyLifecycleReconcilePayload:
    return reconcile_lifecycle_with_alpha_validation_from_lifecycle(
        session,
        lifecycle=get_strategy_lifecycle(session),
        reconciled_by="system_reconcile",
        reason="Alpha validation is not ready for the current lifecycle stage.",
    )


def reconcile_lifecycle_with_alpha_validation_from_lifecycle(
    session: Session,
    *,
    lifecycle: StrategyLifecyclePayload,
    reconciled_by: str,
    reason: str,
) -> StrategyLifecycleReconcilePayload:
    previous_stage = lifecycle.current_stage
    alpha_ready = _alpha_ready(lifecycle)
    if previous_stage not in {"shadow_candidate", "shadow", "live_small", "live"} or alpha_ready:
        return StrategyLifecycleReconcilePayload(
            strategy_id=lifecycle.strategy_id,
            previous_stage=previous_stage,
            current_stage=previous_stage,
            reconciled=False,
            reconciled_by=reconciled_by,
            reason=reason,
            alpha_ready=alpha_ready,
            auto_promotion_enabled=False,
            execution_enabled=False,
            summary=f"Strategy {lifecycle.strategy_id} lifecycle is already aligned with alpha validation.",
        )

    state = _get_or_create_state(session, lifecycle.strategy_id)
    previous_stage = state.current_stage
    state.current_stage = "paper"
    state.transition_reason = f"lifecycle reconciled by {reconciled_by}: {reason}"
    state.auto_transition_count = 0
    state.updated_at = utc_now()
    session.add(state)
    session.add(
        AuditLog(
            action="strategy_lifecycle_reconciled",
            entity_type="strategy",
            entity_id=lifecycle.strategy_id,
            metadata_json=json.dumps(
                {
                    "approved_by": reconciled_by,
                    "reason": reason,
                    "previous_stage": previous_stage,
                    "current_stage": "paper",
                    "alpha_ready": alpha_ready,
                    "auto_promotion_enabled": False,
                    "execution_enabled": False,
                },
                ensure_ascii=True,
            ),
        )
    )
    session.commit()
    session.refresh(state)
    return StrategyLifecycleReconcilePayload(
        strategy_id=lifecycle.strategy_id,
        previous_stage=previous_stage,
        current_stage=state.current_stage,
        reconciled=True,
        reconciled_by=reconciled_by,
        reason=reason,
        alpha_ready=alpha_ready,
        auto_promotion_enabled=False,
        execution_enabled=False,
        summary=(
            f"Strategy {lifecycle.strategy_id} reconciled from {previous_stage} to paper; "
            "alpha validation remains required before shadow."
        ),
    )


def _get_or_create_state(session: Session, strategy_id: str) -> StrategyLifecycleState:
    state = session.exec(select(StrategyLifecycleState).where(StrategyLifecycleState.strategy_id == strategy_id)).first()
    if state is not None:
        return state
    state = StrategyLifecycleState(strategy_id=strategy_id, current_stage="paper")
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def _alpha_ready(lifecycle: StrategyLifecyclePayload) -> bool:
    alpha_rule = next((rule for rule in lifecycle.rules if rule.name == "alpha_validation_ready"), None)
    return alpha_rule.passed if alpha_rule is not None else False
