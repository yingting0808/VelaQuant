from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import ShadowObservation
from app.services.market_calendar import current_market_trading_day
from app.services.shadow_validation import MIN_SHADOW_OBSERVATIONS
from app.services.workspace import get_or_create_default_workspace


ShadowObservationHealthStatus = Literal["collecting", "stable", "attention", "blocked"]


class ShadowObservationHealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    status: ShadowObservationHealthStatus
    sample_ready: bool
    observation_count: int
    observing_count: int
    blocked_count: int
    consecutive_observing_count: int
    latest_trading_day: str | None
    average_would_route_order_count: float
    average_event_chain_count: float
    average_residual_risk_count: float
    warnings: list[str]
    summary: str


def get_shadow_observation_health(
    session: Session,
    *,
    strategy_id: str = "deterministic_watchlist_v1",
    as_of_trading_day: str | None = None,
) -> ShadowObservationHealthPayload:
    workspace = get_or_create_default_workspace(session)
    as_of_trading_day = as_of_trading_day or _current_trading_day()
    observations = list(
        session.exec(
            select(ShadowObservation)
            .where(ShadowObservation.team_id == workspace.team.id, ShadowObservation.strategy_id == strategy_id)
            .where(ShadowObservation.trading_day <= as_of_trading_day)
            .order_by(ShadowObservation.trading_day)
        ).all()
    )
    return build_shadow_observation_health(strategy_id=strategy_id, observations=observations)


def build_shadow_observation_health(
    *,
    strategy_id: str,
    observations: list[ShadowObservation],
) -> ShadowObservationHealthPayload:
    observation_count = len(observations)
    observing_count = sum(1 for item in observations if item.status == "observing")
    blocked_count = sum(1 for item in observations if item.status == "blocked")
    average_would_route = _average([item.would_route_order_count for item in observations])
    average_event_chain = _average([item.event_chain_count for item in observations])
    average_residual = _average([item.residual_risk_count for item in observations])

    warnings: list[str] = []
    if observing_count < MIN_SHADOW_OBSERVATIONS:
        warnings.append("sample_not_ready")
    if blocked_count > 0:
        warnings.append("blocked_observation")
    if any(item.event_chain_count <= 0 for item in observations):
        warnings.append("event_chain_missing")
    if any(item.observed_intent_count <= 0 for item in observations):
        warnings.append("intent_missing")
    if average_residual > 2:
        warnings.append("residual_risk_high")

    sample_ready = (
        observing_count >= MIN_SHADOW_OBSERVATIONS
        and blocked_count == 0
        and "event_chain_missing" not in warnings
        and "intent_missing" not in warnings
    )
    status: ShadowObservationHealthStatus
    if "blocked_observation" in warnings or "event_chain_missing" in warnings:
        status = "blocked"
    elif not sample_ready:
        status = "collecting"
    elif "residual_risk_high" in warnings:
        status = "attention"
    else:
        status = "stable"
    latest = observations[-1] if observations else None
    return ShadowObservationHealthPayload(
        strategy_id=strategy_id,
        status=status,
        sample_ready=sample_ready,
        observation_count=observation_count,
        observing_count=observing_count,
        blocked_count=blocked_count,
        consecutive_observing_count=_consecutive_observing_count(observations),
        latest_trading_day=latest.trading_day if latest is not None else None,
        average_would_route_order_count=average_would_route,
        average_event_chain_count=average_event_chain,
        average_residual_risk_count=average_residual,
        warnings=warnings,
        summary=_summary(status, observing_count, blocked_count, warnings),
    )


def _average(values: list[int]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _consecutive_observing_count(observations: list[ShadowObservation]) -> int:
    count = 0
    for item in reversed(observations):
        if item.status != "observing":
            break
        count += 1
    return count


def _summary(
    status: ShadowObservationHealthStatus,
    observing_count: int,
    blocked_count: int,
    warnings: list[str],
) -> str:
    if status == "stable":
        return f"Shadow observation health is stable with {observing_count} clean observations."
    if status == "blocked":
        return f"Shadow observation health is blocked with {blocked_count} blocked observations; warnings: {', '.join(warnings)}."
    if status == "attention":
        return f"Shadow observation health needs attention; warnings: {', '.join(warnings)}."
    return f"Shadow observation health is collecting samples; {observing_count}/{MIN_SHADOW_OBSERVATIONS} observations recorded."


def _current_trading_day() -> str:
    return current_market_trading_day()
