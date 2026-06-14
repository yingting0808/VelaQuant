from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperOrder, PaperRun
from app.services.market_calendar import current_market_trading_day
from app.services.strategy_event_filters import (
    MANUAL_OVERRIDE_STRATEGY_SUFFIX,
    filter_strategy_trade_events,
    manual_override_correlation_ids,
)
from app.services.strategy_evaluation import DEFAULT_STRATEGY_ID
from app.services.workspace import get_or_create_default_workspace


class StrategyAlphaIsolationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    isolated: bool
    strategy_order_count: int
    manual_override_order_count: int
    manual_override_event_chain_count: int
    filtered_event_chain_count: int
    summary: str


def get_strategy_alpha_isolation(
    session: Session,
    *,
    team_id: UUID | None = None,
    strategy_id: str = DEFAULT_STRATEGY_ID,
    as_of_trading_day: str | None = None,
) -> StrategyAlphaIsolationPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    as_of_trading_day = as_of_trading_day or current_market_trading_day()
    orders = [
        order
        for order in session.exec(select(PaperOrder).where(PaperOrder.team_id == team_id)).all()
        if order.submitted_at.date().isoformat() <= as_of_trading_day
    ]
    eligible_events = _eligible_events(session, team_id, as_of_trading_day)
    manual_correlations = manual_override_correlation_ids(eligible_events)
    filtered_correlations = {
        event.correlation_id
        for event in filter_strategy_trade_events(eligible_events)
    }
    isolated = not manual_correlations.intersection(filtered_correlations)
    strategy_order_count = len([order for order in orders if order.strategy_id == strategy_id])
    manual_order_count = len(
        [
            order
            for order in orders
            if order.strategy_id == f"{strategy_id}{MANUAL_OVERRIDE_STRATEGY_SUFFIX}"
        ]
    )
    return StrategyAlphaIsolationPayload(
        strategy_id=strategy_id,
        isolated=isolated,
        strategy_order_count=strategy_order_count,
        manual_override_order_count=manual_order_count,
        manual_override_event_chain_count=len(manual_correlations),
        filtered_event_chain_count=len(filtered_correlations),
        summary=_summary(isolated, manual_order_count, len(manual_correlations), len(filtered_correlations)),
    )


def _eligible_events(session: Session, team_id: UUID, as_of_trading_day: str) -> list[CoreEventLog]:
    eligible_run_ids = {
        run.id
        for run in session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.trading_day <= as_of_trading_day)
        ).all()
    }
    events = session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id)).all()
    return [
        event
        for event in events
        if event.run_id in eligible_run_ids
        or (event.run_id is None and event.published_at.date().isoformat() <= as_of_trading_day)
    ]


def _summary(
    isolated: bool,
    manual_order_count: int,
    manual_chain_count: int,
    filtered_chain_count: int,
) -> str:
    if isolated:
        return (
            "Manual override activity is isolated from alpha validation: "
            f"{manual_order_count} manual orders, {manual_chain_count} manual chains, "
            f"{filtered_chain_count} strategy chains remain eligible."
        )
    return "Manual override activity is leaking into alpha validation; block promotion until repaired."
