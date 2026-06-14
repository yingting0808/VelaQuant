from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.data.providers.base import (
    EvidenceItem,
    FundamentalSnapshot,
    MarketDataProvider,
    MarketSnapshot,
    PriceHistoryBar,
    ProviderStatus,
    Quote,
)
from app.domain.models import PaperOrder, PaperReview, PaperRun, PaperRunStatus
from app.services.paper_trading import get_paper_trading_summary
from app.services.paper_trading import PaperOrderCreate, submit_paper_order
from app.services.paper_simulation import PaperSimulationRequest, run_paper_simulation_lab


class FixtureProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.prices = {"AAPL": 100.0, "MSFT": 200.0, "NVDA": 50.0, "AMZN": 150.0, "META": 300.0}

    def get_quote(self, ticker: str) -> Quote:
        normalized = ticker.strip().upper()
        return Quote(
            ticker=normalized,
            price=self.prices.get(normalized),
            currency="USD",
            source="fixture",
            updated_at="2026-06-13T00:00:00Z",
            is_fallback=False,
            message="fixture quote",
        )

    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        return []

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker.strip().upper(),
            market_cap=None,
            pe_ratio=None,
            eps=None,
            price_to_sales=None,
            price_to_book=None,
            gross_margin=None,
            profit_margin=None,
            operating_margin=None,
            debt_to_equity=None,
            source="fixture",
            period_ending=None,
            updated_at="2026-06-13T00:00:00Z",
        )

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.strip().upper()
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=[],
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        normalized = ticker.strip().upper()
        counts = {"NVDA": 3, "AAPL": 2, "MSFT": 1, "AMZN": 1, "META": 1}
        return [
            EvidenceItem(
                ticker=normalized,
                title=f"{normalized} evidence {index}",
                summary=f"{normalized} has fixture evidence {index}.",
                source="fixture",
                source_url="https://example.test/evidence",
                observed_at="2026-06-13T00:00:00Z",
            )
            for index in range(1, counts.get(normalized, 0) + 1)
        ]

    def get_statuses(self) -> list[ProviderStatus]:
        return []


def test_paper_simulation_runs_multiple_days_through_daily_loop():
    with make_session() as session:
        result = run_paper_simulation_lab(
            session,
            FixtureProvider(),
            PaperSimulationRequest(start_date="2026-06-14", days=3, scenario="bullish"),
        )

        runs = session.exec(select(PaperRun).order_by(PaperRun.trading_day)).all()
        reviews = session.exec(select(PaperReview).order_by(PaperReview.trading_day)).all()
        assert result.days_requested == 3
        assert result.days_completed == 3
        assert [item.trading_day for item in result.items] == ["2026-06-14", "2026-06-15", "2026-06-16"]
        assert [run.status for run in runs] == [
            PaperRunStatus.completed,
            PaperRunStatus.completed,
            PaperRunStatus.completed,
        ]
        assert [review.trading_day for review in reviews] == ["2026-06-14", "2026-06-15", "2026-06-16"]
        assert result.review_day_count == 3
        assert result.event_chain_count > 0
        assert result.blockers


def test_paper_simulation_does_not_count_real_today_orders_against_future_lab_days():
    with make_session() as session:
        provider = FixtureProvider()
        for ticker in ["AAPL", "MSFT", "NVDA", "AMZN", "META"]:
            submit_paper_order(session, provider, PaperOrderCreate(ticker=ticker, side="buy", quantity=1))

        result = run_paper_simulation_lab(
            session,
            provider,
            PaperSimulationRequest(start_date="2026-06-14", days=2, scenario="bullish"),
        )

        today = datetime.now(timezone.utc).date().isoformat()
        rejected_today = [
            order
            for order in session.exec(select(PaperOrder).where(PaperOrder.rejection_reason == "Orders today 5 reached limit 5.")).all()
            if order.submitted_at.date().isoformat() == today
        ]
        assert rejected_today == []
        assert result.days_completed == 2
        assert result.latest_expectancy > 0


def test_paper_simulation_uses_isolated_account_without_mutating_paper_account():
    with make_session() as session:
        provider = FixtureProvider()
        before = get_paper_trading_summary(session, provider)

        result = run_paper_simulation_lab(
            session,
            provider,
            PaperSimulationRequest(start_date="2026-06-14", days=2, scenario="bullish"),
        )
        after = get_paper_trading_summary(session, provider)
        runs = session.exec(select(PaperRun).order_by(PaperRun.trading_day)).all()

        assert result.days_completed == 2
        assert after.account.id == before.account.id
        assert after.account.cash == before.account.cash
        assert after.orders == []
        assert after.positions == []
        assert all(run.trigger.value == "simulation" for run in runs)


def test_paper_simulation_reports_only_runs_created_by_current_request():
    with make_session() as session:
        provider = FixtureProvider()
        run_paper_simulation_lab(
            session,
            provider,
            PaperSimulationRequest(start_date="2026-06-14", days=2, scenario="bullish"),
        )

        second = run_paper_simulation_lab(
            session,
            provider,
            PaperSimulationRequest(start_date="2026-06-14", days=2, scenario="bullish"),
        )

        assert second.days_completed == 0
        assert second.days_skipped == 2
        assert [item.run_status for item in second.items] == ["skipped", "skipped"]


def test_paper_simulation_default_start_continues_after_latest_review():
    with make_session() as session:
        provider = FixtureProvider()
        run_paper_simulation_lab(
            session,
            provider,
            PaperSimulationRequest(start_date="2026-06-14", days=2, scenario="bullish"),
        )

        result = run_paper_simulation_lab(
            session,
            provider,
            PaperSimulationRequest(days=2, scenario="bullish"),
        )

        assert result.start_date == "2026-06-16"
        assert result.days_completed == 2
        assert [item.trading_day for item in result.items] == ["2026-06-16", "2026-06-17"]


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
