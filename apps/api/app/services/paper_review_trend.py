from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import PaperReadiness, PaperReview
from app.services.market_calendar import current_market_trading_day
from app.services.workspace import get_or_create_default_workspace


class PaperReviewTrendItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trading_day: str
    equity: float
    daily_pnl: float
    daily_return: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int
    win_rate: float
    expectancy: float
    readiness: str


class PaperReviewTrendPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_size: int
    positive_expectancy_days: int
    consecutive_positive_expectancy_days: int
    average_expectancy: float
    latest_expectancy: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    latest_readiness: str
    items: list[PaperReviewTrendItem]
    summary: str


def get_paper_review_trend(
    session: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 10,
    as_of_trading_day: str | None = None,
) -> PaperReviewTrendPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    as_of_trading_day = as_of_trading_day or _current_trading_day()
    bounded_limit = max(1, min(limit, 60))
    raw_reviews = list(
        session.exec(
            select(PaperReview)
            .where(PaperReview.team_id == team_id)
            .where(PaperReview.trading_day <= as_of_trading_day)
            .order_by(PaperReview.trading_day.desc(), PaperReview.created_at.desc())
        ).all()
    )
    reviews = _latest_review_per_trading_day(raw_reviews)[:bounded_limit]
    chronological = sorted(reviews, key=lambda review: review.trading_day)
    sample_size = len(reviews)
    positive_days = sum(1 for review in reviews if review.expectancy > 0)
    consecutive_positive_days = _consecutive_positive_expectancy_days(chronological)
    average_expectancy = _average_expectancy(reviews)
    latest = reviews[0] if reviews else None
    latest_expectancy = round(latest.expectancy, 2) if latest is not None else 0
    latest_readiness = latest.readiness.value if latest is not None else PaperReadiness.collecting.value
    total_realized_pnl = round(latest.realized_pnl, 2) if latest is not None else 0.0
    total_unrealized_pnl = round(latest.unrealized_pnl, 2) if latest is not None else 0.0
    return PaperReviewTrendPayload(
        sample_size=sample_size,
        positive_expectancy_days=positive_days,
        consecutive_positive_expectancy_days=consecutive_positive_days,
        average_expectancy=average_expectancy,
        latest_expectancy=latest_expectancy,
        total_realized_pnl=total_realized_pnl,
        total_unrealized_pnl=total_unrealized_pnl,
        latest_readiness=latest_readiness,
        items=_items(reviews),
        summary=_summary(sample_size, latest_expectancy, average_expectancy, consecutive_positive_days),
    )


def _latest_review_per_trading_day(reviews: list[PaperReview]) -> list[PaperReview]:
    latest_by_day: dict[str, PaperReview] = {}
    sorted_reviews = sorted(reviews, key=lambda review: (review.trading_day, review.created_at), reverse=True)
    for review in sorted_reviews:
        if review.trading_day not in latest_by_day:
            latest_by_day[review.trading_day] = review
    return sorted(latest_by_day.values(), key=lambda review: review.trading_day, reverse=True)


def _items(reviews: list[PaperReview]) -> list[PaperReviewTrendItem]:
    chronological = sorted(reviews, key=lambda review: review.trading_day)
    previous: PaperReview | None = None
    item_by_day: dict[str, PaperReviewTrendItem] = {}
    for review in chronological:
        daily_pnl = round(review.equity - previous.equity, 2) if previous is not None else 0.0
        daily_return = round(daily_pnl / previous.equity, 4) if previous is not None and previous.equity else 0.0
        item_by_day[review.trading_day] = _item(review, daily_pnl=daily_pnl, daily_return=daily_return)
        previous = review
    return [item_by_day[review.trading_day] for review in reviews]


def _item(review: PaperReview, *, daily_pnl: float, daily_return: float) -> PaperReviewTrendItem:
    return PaperReviewTrendItem(
        trading_day=review.trading_day,
        equity=round(review.equity, 2),
        daily_pnl=daily_pnl,
        daily_return=daily_return,
        cash=round(review.cash, 2),
        realized_pnl=round(review.realized_pnl, 2),
        unrealized_pnl=round(review.unrealized_pnl, 2),
        trade_count=review.trade_count,
        win_rate=review.win_rate,
        expectancy=round(review.expectancy, 2),
        readiness=review.readiness.value,
    )


def _average_expectancy(reviews: list[PaperReview]) -> float:
    if not reviews:
        return 0
    return round(sum(review.expectancy for review in reviews) / len(reviews), 2)


def _consecutive_positive_expectancy_days(reviews: list[PaperReview]) -> int:
    count = 0
    for review in reversed(reviews):
        if review.expectancy <= 0:
            break
        count += 1
    return count


def _summary(
    sample_size: int,
    latest_expectancy: float,
    average_expectancy: float,
    consecutive_positive_days: int,
) -> str:
    if sample_size <= 0:
        return "No paper reviews are available yet."
    if latest_expectancy > 0 and average_expectancy > 0:
        return (
            f"Paper review trend is positive: latest expectancy {latest_expectancy:.2f}, "
            f"average {average_expectancy:.2f}, consecutive positive days {consecutive_positive_days}."
        )
    return (
        f"Paper review trend is not validated: latest expectancy {latest_expectancy:.2f}, "
        f"average {average_expectancy:.2f}, consecutive positive days {consecutive_positive_days}."
    )


def _current_trading_day() -> str:
    return current_market_trading_day()
