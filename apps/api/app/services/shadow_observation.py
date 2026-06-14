from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import PaperReview, ShadowObservation
from app.services.event_ledger import EventLedgerStatus, get_event_ledger_status
from app.services.market_calendar import current_market_trading_day
from app.services.shadow_review import ShadowReviewPayload, get_shadow_review_packet
from app.services.strategy_lifecycle import get_strategy_lifecycle
from app.services.workspace import get_or_create_default_workspace


class ShadowObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    team_id: UUID
    strategy_id: str
    trading_day: str
    status: str
    can_request_shadow_review: bool
    observed_intent_count: int
    would_route_order_count: int
    event_chain_count: int
    residual_risk_count: int
    blocked_reason: str | None
    created_at: str


class ShadowObservationSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_record_shadow_observation: bool
    latest: ShadowObservationPayload | None
    items: list[ShadowObservationPayload]
    summary: str


def get_shadow_observations(
    session: Session,
    *,
    as_of_trading_day: str | None = None,
) -> ShadowObservationSummaryPayload:
    workspace = get_or_create_default_workspace(session)
    as_of_trading_day = as_of_trading_day or current_market_trading_day()
    lifecycle = get_strategy_lifecycle(session)
    shadow_review = get_shadow_review_packet(session)
    items = [
        _payload(item)
        for item in session.exec(
            select(ShadowObservation)
            .where(ShadowObservation.team_id == workspace.team.id)
            .where(ShadowObservation.trading_day <= as_of_trading_day)
            .order_by(ShadowObservation.created_at.desc())
        ).all()
    ]
    latest = items[0] if items else None
    return ShadowObservationSummaryPayload(
        can_record_shadow_observation=lifecycle.current_stage == "shadow" and shadow_review.can_request_shadow_review,
        latest=latest,
        items=items[:20],
        summary=_summary(latest, len(items)),
    )


def record_shadow_observation(session: Session) -> ShadowObservationPayload:
    workspace = get_or_create_default_workspace(session)
    as_of_trading_day = current_market_trading_day()
    event_ledger = get_event_ledger_status(session)
    lifecycle = get_strategy_lifecycle(session)
    trading_day = _latest_trading_day(session, workspace.team.id, as_of_trading_day=as_of_trading_day)
    return record_shadow_observation_from_packet(
        session,
        team_id=workspace.team.id,
        trading_day=trading_day,
        current_stage=lifecycle.current_stage,
        shadow_review=get_shadow_review_packet(session),
        event_ledger=event_ledger,
    )


def record_shadow_observation_from_packet(
    session: Session,
    *,
    team_id: UUID,
    trading_day: str,
    current_stage: str,
    shadow_review: ShadowReviewPayload,
    event_ledger: EventLedgerStatus,
) -> ShadowObservationPayload:
    if current_stage != "shadow":
        raise ValueError("Shadow observation requires current lifecycle stage shadow.")

    existing = session.exec(
        select(ShadowObservation).where(
            ShadowObservation.team_id == team_id,
            ShadowObservation.strategy_id == shadow_review.strategy_id,
            ShadowObservation.trading_day == trading_day,
        )
    ).first()
    if existing is not None:
        return _payload(existing)

    observation = ShadowObservation(
        team_id=team_id,
        strategy_id=shadow_review.strategy_id,
        trading_day=trading_day,
        status="observing" if shadow_review.can_request_shadow_review else "blocked",
        can_request_shadow_review=shadow_review.can_request_shadow_review,
        observed_intent_count=_topic_count(event_ledger, "trade_intent"),
        would_route_order_count=_would_route_order_count(event_ledger),
        event_chain_count=event_ledger.latest_correlation_count,
        residual_risk_count=len(shadow_review.residual_risks),
        blocked_reason=None if shadow_review.can_request_shadow_review else shadow_review.summary,
    )
    session.add(observation)
    session.commit()
    session.refresh(observation)
    return _payload(observation)


def _payload(observation: ShadowObservation) -> ShadowObservationPayload:
    return ShadowObservationPayload(
        id=observation.id,
        team_id=observation.team_id,
        strategy_id=observation.strategy_id,
        trading_day=observation.trading_day,
        status=observation.status,
        can_request_shadow_review=observation.can_request_shadow_review,
        observed_intent_count=observation.observed_intent_count,
        would_route_order_count=observation.would_route_order_count,
        event_chain_count=observation.event_chain_count,
        residual_risk_count=observation.residual_risk_count,
        blocked_reason=observation.blocked_reason,
        created_at=observation.created_at.isoformat(),
    )


def _topic_count(event_ledger: EventLedgerStatus, topic: str) -> int:
    for item in event_ledger.latest_topic_counts:
        if item.topic == topic:
            return item.count
    return 0


def _would_route_order_count(event_ledger: EventLedgerStatus) -> int:
    if event_ledger.latest_replay is None:
        return 0
    return sum(1 for chain in event_ledger.latest_replay.chains if chain.terminal_state is not None)


def _latest_trading_day(
    session: Session,
    team_id: UUID,
    *,
    as_of_trading_day: str | None = None,
) -> str:
    as_of_trading_day = as_of_trading_day or current_market_trading_day()
    review = session.exec(
        select(PaperReview)
        .where(PaperReview.team_id == team_id)
        .where(PaperReview.trading_day <= as_of_trading_day)
        .order_by(PaperReview.trading_day.desc(), PaperReview.created_at.desc())
    ).first()
    if review is not None:
        return review.trading_day
    return current_market_trading_day()


def _summary(latest: ShadowObservationPayload | None, total_count: int) -> str:
    if latest is None:
        return "No shadow observations have been recorded yet."
    return (
        f"Shadow observation latest {latest.status} on {latest.trading_day}; "
        f"{total_count} observations recorded, no broker orders created."
    )
