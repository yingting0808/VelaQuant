from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.shadow_observation_health import ShadowObservationHealthPayload, get_shadow_observation_health
from app.services.shadow_review import ShadowReviewPayload, get_shadow_review_packet
from app.services.shadow_validation import ShadowValidationPayload, get_shadow_validation
from app.services.strategy_lifecycle import StrategyLifecyclePayload, get_strategy_lifecycle


LiveSmallReviewStatus = Literal["blocked", "ready_for_manual_review"]
LiveSmallReviewRiskSeverity = Literal["info", "medium", "high"]


class LiveSmallReviewChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    passed: bool
    evidence: list[str]


class LiveSmallReviewResidualRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: LiveSmallReviewRiskSeverity
    detail: str
    evidence: list[str]


class LiveSmallReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LiveSmallReviewStatus
    strategy_id: str
    can_request_live_small_review: bool
    recommended_stage: str
    auto_promotion_enabled: bool
    checklist: list[LiveSmallReviewChecklistItem]
    residual_risks: list[LiveSmallReviewResidualRisk]
    summary: str


def get_live_small_review_packet(session: Session) -> LiveSmallReviewPayload:
    return build_live_small_review_packet(
        lifecycle=get_strategy_lifecycle(session),
        shadow_validation=get_shadow_validation(session),
        shadow_health=get_shadow_observation_health(session),
        shadow_review=get_shadow_review_packet(session),
    )


def build_live_small_review_packet(
    *,
    lifecycle: StrategyLifecyclePayload,
    shadow_validation: ShadowValidationPayload,
    shadow_health: ShadowObservationHealthPayload,
    shadow_review: ShadowReviewPayload,
) -> LiveSmallReviewPayload:
    checklist = [
        _check(
            "current_stage_shadow",
            "当前处于 Shadow",
            lifecycle.current_stage == "shadow",
            [f"current_stage={lifecycle.current_stage}", "manual shadow approval required before live-small review"],
        ),
        _check(
            "shadow_review_completed",
            "Shadow 评审已通过",
            shadow_review.status == "ready_for_manual_review" and shadow_review.can_request_shadow_review,
            [shadow_review.summary],
        ),
        _check(
            "shadow_validation_passed",
            "Shadow 验证通过",
            shadow_validation.shadow_ready and shadow_validation.status == "shadow_validated",
            [shadow_validation.summary],
        ),
        _check(
            "shadow_observation_sample",
            "Shadow 观察样本充足",
            shadow_validation.observing_count >= shadow_validation.min_observations_required
            and shadow_validation.blocked_count == 0,
            [
                f"observing={shadow_validation.observing_count}",
                f"required={shadow_validation.min_observations_required}",
                f"blocked={shadow_validation.blocked_count}",
            ],
        ),
        _check(
            "shadow_health_stable",
            "Shadow 健康稳定",
            shadow_health.sample_ready and shadow_health.status == "stable",
            [
                shadow_health.summary,
                f"status={shadow_health.status}",
                f"warnings={','.join(shadow_health.warnings) or 'none'}",
            ],
        ),
        _check(
            "auto_promotion_disabled",
            "自动晋级关闭",
            not lifecycle.auto_actions_enabled and not shadow_review.auto_promotion_enabled,
            [
                f"lifecycle_auto_actions={lifecycle.auto_actions_enabled}",
                f"shadow_review_auto_promotion={shadow_review.auto_promotion_enabled}",
            ],
        ),
    ]
    can_request = all(item.passed for item in checklist)
    status: LiveSmallReviewStatus = "ready_for_manual_review" if can_request else "blocked"
    return LiveSmallReviewPayload(
        status=status,
        strategy_id=lifecycle.strategy_id,
        can_request_live_small_review=can_request,
        recommended_stage="live_small" if can_request else "shadow",
        auto_promotion_enabled=False,
        checklist=checklist,
        residual_risks=_residual_risks(shadow_validation),
        summary=_summary(status),
    )


def _check(code: str, label: str, passed: bool, evidence: list[str]) -> LiveSmallReviewChecklistItem:
    return LiveSmallReviewChecklistItem(code=code, label=label, passed=passed, evidence=evidence)


def _residual_risks(shadow_validation: ShadowValidationPayload) -> list[LiveSmallReviewResidualRisk]:
    risks = [
        LiveSmallReviewResidualRisk(
            code="live_small_requires_separate_manual_approval",
            severity="info",
            detail="Live-small 只能作为人工评审结论，不能由系统自动晋级或自动实盘下单。",
            evidence=["auto_promotion_enabled=false", "broker execution remains outside this review packet"],
        )
    ]
    if shadow_validation.residual_risk_count > 0:
        risks.append(
            LiveSmallReviewResidualRisk(
                code="shadow_residual_risk_carryover",
                severity="medium",
                detail="Shadow 观察仍带有残余风险记录，live-small 前需要人工复核容量与拒单原因。",
                evidence=[f"residual_risk_count={shadow_validation.residual_risk_count}"],
            )
        )
    if shadow_validation.blocked_count > 0:
        risks.append(
            LiveSmallReviewResidualRisk(
                code="blocked_shadow_observation",
                severity="high",
                detail="存在 blocked Shadow 观察，不能进入 live-small 评审。",
                evidence=[f"blocked_count={shadow_validation.blocked_count}"],
            )
        )
    return risks


def _summary(status: LiveSmallReviewStatus) -> str:
    if status == "ready_for_manual_review":
        return "Live-small review packet is ready for manual review; no automatic promotion or broker order is enabled."
    return "Live-small review packet is blocked; remain in Shadow or paper workflow until all gates pass."
