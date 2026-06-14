from typing import Literal
from uuid import UUID
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperOrder, PaperOrderSide, PaperOrderStatus, PaperReview, PaperRun
from app.services.lean_backtest import read_backtest_history, read_latest_backtest
from app.services.market_calendar import current_market_trading_day
from app.services.strategy_attribution import attribute_current_paper_strategy
from app.services.strategy_event_filters import filter_strategy_trade_events
from app.services.strategy_evaluation import DEFAULT_STRATEGY_ID
from app.services.workspace import get_or_create_default_workspace


MIN_REVIEW_DAYS = 5
MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS = 5
MIN_FILLED_ORDERS = 30
MIN_CLOSED_TRADES = 10
MAX_VALIDATION_DRAWDOWN = 0.15

AlphaValidationLevel = Literal["collecting", "paper_validated", "failed"]


class AlphaValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    alpha_ready: bool
    validation_level: AlphaValidationLevel
    blockers: list[str]
    review_day_count: int
    consecutive_positive_expectancy_days: int
    filled_order_count: int
    closed_trade_count: int
    event_chain_count: int
    has_real_market_backtest: bool
    latest_expectancy: float
    average_expectancy: float
    max_drawdown: float
    score_pnl_inversion_count: int = 0
    summary: str


def get_alpha_validation(
    session: Session,
    *,
    team_id: UUID | None = None,
    strategy_id: str = "deterministic_watchlist_v1",
    as_of_trading_day: str | None = None,
) -> AlphaValidationPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    as_of_trading_day = as_of_trading_day or _current_trading_day()
    reviews = list(
        session.exec(
            select(PaperReview)
            .where(PaperReview.team_id == team_id)
            .where(PaperReview.trading_day <= as_of_trading_day)
            .order_by(PaperReview.trading_day)
        ).all()
    )
    orders = [
        order
        for order in session.exec(select(PaperOrder).where(PaperOrder.team_id == team_id)).all()
        if order.strategy_id == strategy_id
        and order.submitted_at.date().isoformat() <= as_of_trading_day
    ]
    event_chain_count = _event_chain_count_as_of(session, team_id, as_of_trading_day)
    score_pnl_inversion_count = _score_pnl_inversion_count_as_of(
        session,
        team_id=team_id,
        strategy_id=strategy_id,
        as_of_trading_day=as_of_trading_day,
    )
    return build_alpha_validation(
        reviews=reviews,
        orders=orders,
        event_chain_count=event_chain_count,
        has_real_market_backtest=_has_real_market_backtest(strategy_id),
        strategy_id=strategy_id,
        score_pnl_inversion_count=score_pnl_inversion_count,
    )


def build_alpha_validation(
    *,
    reviews: list[PaperReview],
    orders: list[PaperOrder],
    event_chain_count: int,
    has_real_market_backtest: bool = False,
    strategy_id: str = "deterministic_watchlist_v1",
    score_pnl_inversion_count: int = 0,
) -> AlphaValidationPayload:
    sorted_reviews = sorted(_latest_review_per_trading_day(reviews), key=lambda review: review.trading_day)
    filled_orders = [order for order in orders if order.status == PaperOrderStatus.filled]
    closed_orders = [order for order in filled_orders if order.side == PaperOrderSide.sell]
    review_day_count = len({review.trading_day for review in sorted_reviews})
    consecutive_positive_days = _consecutive_positive_expectancy_days(sorted_reviews)
    latest_expectancy = round(sorted_reviews[-1].expectancy, 2) if sorted_reviews else 0.0
    average_expectancy = round(
        sum(review.expectancy for review in sorted_reviews) / len(sorted_reviews),
        2,
    ) if sorted_reviews else 0.0
    max_drawdown = _max_drawdown(sorted_reviews)
    blockers = _blockers(
        review_day_count=review_day_count,
        consecutive_positive_days=consecutive_positive_days,
        filled_order_count=len(filled_orders),
        closed_trade_count=len(closed_orders),
        event_chain_count=event_chain_count,
        has_real_market_backtest=has_real_market_backtest,
        latest_expectancy=latest_expectancy,
        average_expectancy=average_expectancy,
        max_drawdown=max_drawdown,
        score_pnl_inversion_count=score_pnl_inversion_count,
    )
    alpha_ready = not blockers
    validation_level: AlphaValidationLevel = "paper_validated" if alpha_ready else "collecting"
    if review_day_count >= MIN_REVIEW_DAYS and latest_expectancy < 0 and average_expectancy < 0:
        validation_level = "failed"
    return AlphaValidationPayload(
        strategy_id=strategy_id,
        alpha_ready=alpha_ready,
        validation_level=validation_level,
        blockers=blockers,
        review_day_count=review_day_count,
        consecutive_positive_expectancy_days=consecutive_positive_days,
        filled_order_count=len(filled_orders),
        closed_trade_count=len(closed_orders),
        event_chain_count=event_chain_count,
        has_real_market_backtest=has_real_market_backtest,
        latest_expectancy=latest_expectancy,
        average_expectancy=average_expectancy,
        max_drawdown=max_drawdown,
        score_pnl_inversion_count=score_pnl_inversion_count,
        summary=_summary(alpha_ready, validation_level, blockers),
    )


def _latest_review_per_trading_day(reviews: list[PaperReview]) -> list[PaperReview]:
    latest_by_day: dict[str, PaperReview] = {}
    sorted_reviews = sorted(reviews, key=lambda review: (review.trading_day, _datetime_sort_key(review.created_at)), reverse=True)
    for review in sorted_reviews:
        if review.trading_day not in latest_by_day:
            latest_by_day[review.trading_day] = review
    return sorted(latest_by_day.values(), key=lambda review: review.trading_day)


def _datetime_sort_key(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).timestamp()


def _blockers(
    *,
    review_day_count: int,
    consecutive_positive_days: int,
    filled_order_count: int,
    closed_trade_count: int,
    event_chain_count: int,
    has_real_market_backtest: bool,
    latest_expectancy: float,
    average_expectancy: float,
    max_drawdown: float,
    score_pnl_inversion_count: int,
) -> list[str]:
    blockers: list[str] = []
    if review_day_count < MIN_REVIEW_DAYS:
        blockers.append("review_day_sample")
    if consecutive_positive_days < MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS:
        blockers.append("consecutive_positive_expectancy")
    if filled_order_count < MIN_FILLED_ORDERS:
        blockers.append("filled_order_sample")
    if closed_trade_count < MIN_CLOSED_TRADES:
        blockers.append("closed_trade_sample")
    if event_chain_count <= 0:
        blockers.append("event_ledger_populated")
    if not has_real_market_backtest:
        blockers.append("real_market_backtest")
    if latest_expectancy <= 0:
        blockers.append("latest_positive_expectancy")
    if average_expectancy <= 0:
        blockers.append("average_positive_expectancy")
    if max_drawdown > MAX_VALIDATION_DRAWDOWN:
        blockers.append("drawdown_limit")
    if score_pnl_inversion_count > 0:
        blockers.append("score_pnl_inversion_review")
    return blockers


def _has_real_market_backtest(strategy_id: str) -> bool:
    latest = read_latest_backtest()
    if (
        latest is not None
        and latest.strategy_id == strategy_id
        and latest.status == "success"
        and latest.uses_real_market_data
    ):
        return True
    return any(
        item.strategy_id == strategy_id
        and item.status == "success"
        and item.uses_real_market_data
        for item in read_backtest_history()
    )


def _consecutive_positive_expectancy_days(reviews: list[PaperReview]) -> int:
    count = 0
    for review in reversed(reviews):
        if review.expectancy <= 0:
            break
        count += 1
    return count


def _max_drawdown(reviews: list[PaperReview]) -> float:
    peak = 0.0
    worst = 0.0
    for review in reviews:
        peak = max(peak, review.equity)
        if peak <= 0:
            continue
        worst = max(worst, (peak - review.equity) / peak)
    return round(worst, 4)


def _summary(alpha_ready: bool, validation_level: AlphaValidationLevel, blockers: list[str]) -> str:
    if alpha_ready:
        return "Paper alpha validation passed: consecutive positive expectancy, closed trades, event ledger, and drawdown gates are satisfied."
    if validation_level == "failed":
        return "Paper alpha validation failed: expectancy is negative across the validation window."
    return f"Paper alpha validation is collecting evidence; blockers: {', '.join(blockers) or 'none'}."


def _event_chain_count_as_of(session: Session, team_id: UUID, as_of_trading_day: str) -> int:
    eligible_run_ids = {
        run.id
        for run in session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.trading_day <= as_of_trading_day)
        ).all()
    }
    events = session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id)).all()
    eligible_events = [
        event
        for event in events
        if event.run_id in eligible_run_ids
        or (event.run_id is None and event.published_at.date().isoformat() <= as_of_trading_day)
    ]
    return len(
        {
            event.correlation_id
            for event in filter_strategy_trade_events(eligible_events)
        }
    )


def _score_pnl_inversion_count_as_of(
    session: Session,
    *,
    team_id: UUID,
    strategy_id: str,
    as_of_trading_day: str,
) -> int:
    if strategy_id != DEFAULT_STRATEGY_ID:
        return 0
    attribution = attribute_current_paper_strategy(
        session,
        team_id=team_id,
        as_of_trading_day=as_of_trading_day,
    )
    return sum(1 for item in attribution.ticker_diagnostics if item.score_pnl_alignment == "inverted")


def _current_trading_day() -> str:
    return current_market_trading_day()
