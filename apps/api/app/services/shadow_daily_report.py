from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.live_small_review import LiveSmallReviewPayload, get_live_small_review_packet
from app.services.shadow_observation import ShadowObservationSummaryPayload, get_shadow_observations
from app.services.shadow_observation_health import ShadowObservationHealthPayload, get_shadow_observation_health
from app.services.shadow_validation import ShadowValidationPayload, get_shadow_validation


ShadowDailyReportStatus = Literal["collecting", "ready_for_manual_review", "attention", "blocked"]


class ShadowDailyReportAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int
    action_code: str
    title: str
    detail: str
    evidence: list[str]


class ShadowDailyReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    trading_day: str | None
    status: ShadowDailyReportStatus
    observation_status: str
    health_status: str
    validation_status: str
    live_small_status: str
    observed_intent_count: int
    would_route_order_count: int
    event_chain_count: int
    residual_risk_count: int
    remaining_observations: int
    warnings: list[str]
    blockers: list[str]
    next_actions: list[ShadowDailyReportAction]
    live_or_broker_execution_enabled: bool
    summary: str


def get_shadow_daily_report(session: Session) -> ShadowDailyReportPayload:
    return build_shadow_daily_report(
        observations=get_shadow_observations(session),
        health=get_shadow_observation_health(session),
        validation=get_shadow_validation(session),
        live_small_review=get_live_small_review_packet(session),
    )


def build_shadow_daily_report(
    *,
    observations: ShadowObservationSummaryPayload,
    health: ShadowObservationHealthPayload,
    validation: ShadowValidationPayload,
    live_small_review: LiveSmallReviewPayload,
) -> ShadowDailyReportPayload:
    latest = observations.latest
    status = _status(observations, health, validation, live_small_review)
    return ShadowDailyReportPayload(
        strategy_id=validation.strategy_id,
        trading_day=_trading_day(observations, health, validation),
        status=status,
        observation_status=latest.status if latest is not None else "not_recorded",
        health_status=health.status,
        validation_status=validation.status,
        live_small_status=live_small_review.status,
        observed_intent_count=latest.observed_intent_count if latest is not None else 0,
        would_route_order_count=latest.would_route_order_count if latest is not None else 0,
        event_chain_count=latest.event_chain_count if latest is not None else 0,
        residual_risk_count=latest.residual_risk_count if latest is not None else validation.residual_risk_count,
        remaining_observations=validation.remaining_observations,
        warnings=health.warnings,
        blockers=validation.blockers,
        next_actions=_next_actions(status, observations, health, validation, live_small_review),
        live_or_broker_execution_enabled=False,
        summary=_summary(status, observations, validation),
    )


def _status(
    observations: ShadowObservationSummaryPayload,
    health: ShadowObservationHealthPayload,
    validation: ShadowValidationPayload,
    live_small_review: LiveSmallReviewPayload,
) -> ShadowDailyReportStatus:
    if health.status == "blocked" or validation.status == "blocked":
        return "blocked"
    if observations.latest is not None and observations.latest.status == "blocked":
        return "blocked"
    if live_small_review.can_request_live_small_review:
        return "ready_for_manual_review"
    if health.status == "attention":
        return "attention"
    return "collecting"


def _trading_day(
    observations: ShadowObservationSummaryPayload,
    health: ShadowObservationHealthPayload,
    validation: ShadowValidationPayload,
) -> str | None:
    if observations.latest is not None:
        return observations.latest.trading_day
    return health.latest_trading_day or validation.latest_trading_day


def _next_actions(
    status: ShadowDailyReportStatus,
    observations: ShadowObservationSummaryPayload,
    health: ShadowObservationHealthPayload,
    validation: ShadowValidationPayload,
    live_small_review: LiveSmallReviewPayload,
) -> list[ShadowDailyReportAction]:
    if observations.latest is None:
        return [
            ShadowDailyReportAction(
                priority=1,
                action_code="record_shadow_observation",
                title="记录 Shadow 观察",
                detail="当前没有 Shadow 观察记录；先记录一条观察样本，再进入健康与验证判断。",
                evidence=[observations.summary],
            )
        ]
    if status == "blocked":
        return [
            ShadowDailyReportAction(
                priority=1,
                action_code="repair_shadow_event_chain",
                title="修复 Shadow 事件链",
                detail="Shadow 观察或事件链存在阻断，解除前不能进入 live-small 评审。",
                evidence=[health.summary, validation.summary],
            )
        ]
    if status == "ready_for_manual_review":
        return [
            ShadowDailyReportAction(
                priority=1,
                action_code="manual_live_small_review",
                title="提交 live-small 人工评审",
                detail="Shadow 样本和健康门禁已通过；只能由人工评审决定是否进入 live-small。",
                evidence=[live_small_review.summary, "auto_promotion_enabled=false"],
            )
        ]
    if status == "attention":
        return [
            ShadowDailyReportAction(
                priority=1,
                action_code="review_shadow_residual_risk",
                title="复核 Shadow 残余风险",
                detail="Shadow 样本已接近可用，但健康指标需要人工复核。",
                evidence=[health.summary, f"warnings={','.join(health.warnings) or 'none'}"],
            )
        ]
    return [
        ShadowDailyReportAction(
            priority=1,
            action_code="continue_shadow_observation",
            title="继续记录 Shadow 观察",
            detail=f"还需要 {validation.remaining_observations} 条 observing 样本，保持 broker 执行关闭。",
            evidence=[validation.summary, health.summary],
        )
    ]


def _summary(
    status: ShadowDailyReportStatus,
    observations: ShadowObservationSummaryPayload,
    validation: ShadowValidationPayload,
) -> str:
    if observations.latest is None:
        return "Shadow daily report is waiting for the first observation record."
    if status == "ready_for_manual_review":
        return "Shadow daily report is ready for manual live-small review; no automatic promotion is enabled."
    if status == "blocked":
        return "Shadow daily report is blocked; repair event chain or blocked observations before continuing."
    if status == "attention":
        return "Shadow daily report needs attention before live-small review."
    return f"Shadow daily report is collecting observations; {validation.remaining_observations} more samples required."
