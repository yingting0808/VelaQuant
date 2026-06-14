from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import ShadowObservation
from app.services.market_calendar import current_market_trading_day
from app.services.workspace import get_or_create_default_workspace


MIN_SHADOW_OBSERVATIONS = 5
ShadowValidationStatus = Literal["collecting", "shadow_validated", "blocked"]


class ShadowValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    shadow_ready: bool
    status: ShadowValidationStatus
    observation_count: int
    observing_count: int
    blocked_count: int
    latest_trading_day: str | None
    min_observations_required: int
    remaining_observations: int
    residual_risk_count: int
    blockers: list[str]
    summary: str


def get_shadow_validation(
    session: Session,
    *,
    strategy_id: str = "deterministic_watchlist_v1",
    as_of_trading_day: str | None = None,
) -> ShadowValidationPayload:
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
    return build_shadow_validation(strategy_id=strategy_id, observations=observations)


def build_shadow_validation(
    *,
    strategy_id: str,
    observations: list[ShadowObservation],
) -> ShadowValidationPayload:
    observation_count = len(observations)
    observing_count = sum(1 for item in observations if item.status == "observing")
    blocked_count = sum(1 for item in observations if item.status == "blocked")
    remaining = max(0, MIN_SHADOW_OBSERVATIONS - observing_count)
    blockers: list[str] = []
    if blocked_count > 0:
        blockers.append("shadow_observation_blocked")
    if observing_count < MIN_SHADOW_OBSERVATIONS:
        blockers.append("shadow_observation_sample")
    shadow_ready = not blockers
    status: ShadowValidationStatus
    if blocked_count > 0:
        status = "blocked"
    elif shadow_ready:
        status = "shadow_validated"
    else:
        status = "collecting"
    latest = observations[-1] if observations else None
    return ShadowValidationPayload(
        strategy_id=strategy_id,
        shadow_ready=shadow_ready,
        status=status,
        observation_count=observation_count,
        observing_count=observing_count,
        blocked_count=blocked_count,
        latest_trading_day=latest.trading_day if latest is not None else None,
        min_observations_required=MIN_SHADOW_OBSERVATIONS,
        remaining_observations=remaining,
        residual_risk_count=sum(item.residual_risk_count for item in observations),
        blockers=blockers,
        summary=_summary(shadow_ready, status, observing_count, remaining, blockers),
    )


def _summary(
    shadow_ready: bool,
    status: ShadowValidationStatus,
    observing_count: int,
    remaining: int,
    blockers: list[str],
) -> str:
    if shadow_ready:
        return f"Shadow validation passed with {observing_count} observing samples; live-small review can be considered manually."
    if status == "blocked":
        return f"Shadow validation is blocked; blockers: {', '.join(blockers)}."
    return f"Shadow validation is collecting observations; {remaining} more observing samples required."


def _current_trading_day() -> str:
    return current_market_trading_day()
