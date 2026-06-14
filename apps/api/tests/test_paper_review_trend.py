from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import PaperAccount, PaperReadiness, PaperReview, Team
from app.services.paper_review_trend import get_paper_review_trend


def test_paper_review_trend_aggregates_expectancy_window():
    with make_session() as session:
        team = Team(name="Review Trend")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(_review(account, "2026-06-11", expectancy=-0.5, equity=99900, readiness=PaperReadiness.collecting))
        session.add(_review(account, "2026-06-12", expectancy=1.2, equity=100100, readiness=PaperReadiness.watch))
        session.add(_review(account, "2026-06-13", expectancy=1.4, equity=100350, readiness=PaperReadiness.watch))
        session.commit()

        trend = get_paper_review_trend(session, team_id=team.id, limit=10)

        assert trend.sample_size == 3
        assert trend.positive_expectancy_days == 2
        assert trend.consecutive_positive_expectancy_days == 2
        assert trend.average_expectancy == 0.7
        assert trend.latest_expectancy == 1.4
        assert trend.latest_readiness == "watch"
        assert trend.items[0].trading_day == "2026-06-13"
        assert trend.items[2].expectancy == -0.5


def test_paper_review_trend_handles_empty_reviews():
    with make_session() as session:
        team = Team(name="Empty Trend")
        session.add(team)
        session.commit()
        session.refresh(team)

        trend = get_paper_review_trend(session, team_id=team.id)

        assert trend.sample_size == 0
        assert trend.positive_expectancy_days == 0
        assert trend.consecutive_positive_expectancy_days == 0
        assert trend.average_expectancy == 0
        assert trend.latest_expectancy == 0
        assert trend.latest_readiness == "collecting"
        assert trend.items == []


def test_paper_review_trend_uses_latest_review_per_trading_day():
    with make_session() as session:
        team = Team(name="Dedup Trend")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        old_review = _review(account, "2026-06-13", expectancy=-1.0, equity=99000, readiness=PaperReadiness.collecting)
        old_review.created_at = datetime(2026, 6, 13, 1, 0, tzinfo=timezone.utc)
        latest_review = _review(account, "2026-06-13", expectancy=2.0, equity=101000, readiness=PaperReadiness.watch)
        latest_review.created_at = datetime(2026, 6, 13, 2, 0, tzinfo=timezone.utc)
        prior_day = _review(account, "2026-06-12", expectancy=1.0, equity=100500, readiness=PaperReadiness.watch)
        prior_day.created_at = datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)
        session.add(old_review)
        session.add(latest_review)
        session.add(prior_day)
        session.commit()

        trend = get_paper_review_trend(session, team_id=team.id, limit=10)

        assert trend.sample_size == 2
        assert trend.positive_expectancy_days == 2
        assert trend.consecutive_positive_expectancy_days == 2
        assert trend.average_expectancy == 1.5
        assert trend.latest_expectancy == 2.0
        assert [item.trading_day for item in trend.items] == ["2026-06-13", "2026-06-12"]
        assert trend.items[0].expectancy == 2.0


def test_paper_review_trend_ignores_future_reviews_for_as_of_baseline():
    with make_session() as session:
        team = Team(name="As Of Trend")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(_review(account, "2026-06-13", expectancy=0.0, equity=100000, readiness=PaperReadiness.collecting))
        session.add(_review(account, "2026-06-30", expectancy=49.8, equity=103000, readiness=PaperReadiness.watch))
        session.commit()

        trend = get_paper_review_trend(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert trend.sample_size == 1
        assert trend.latest_expectancy == 0
        assert trend.items[0].trading_day == "2026-06-13"


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _review(
    account: PaperAccount,
    trading_day: str,
    *,
    expectancy: float,
    equity: float,
    readiness: PaperReadiness,
) -> PaperReview:
    return PaperReview(
        id=uuid4(),
        account_id=account.id,
        team_id=account.team_id,
        trading_day=trading_day,
        equity=equity,
        cash=90000,
        realized_pnl=10,
        unrealized_pnl=20,
        trade_count=1,
        win_rate=0.5,
        average_win=20,
        average_loss=-10,
        expectancy=expectancy,
        readiness=readiness,
        notes="fixture",
    )
