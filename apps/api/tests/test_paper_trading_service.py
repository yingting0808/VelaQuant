import pytest
import json
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
from app.domain.models import CoreEventLog, PaperOrder, PaperReview, PaperRun, PaperRunStatus, PaperRunTrigger
from app.services.paper_trading import (
    PaperOrderCreate,
    get_paper_trading_summary,
    list_paper_run_events,
    list_paper_runs,
    run_daily_paper_trading_loop,
    submit_paper_order,
)


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


class FailingQuoteProvider(FixtureProvider):
    def get_quote(self, ticker: str) -> Quote:
        raise RuntimeError(f"quote source failed for {ticker}")


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_daily_run_creates_account_candidates_and_review():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider())
        runs = session.exec(select(PaperRun)).all()

        assert summary.account.name == "默认模拟盘"
        assert summary.account.mode == "paper"
        assert summary.account.cash < 100000.0
        assert summary.candidates
        assert summary.candidates[0].ticker == "NVDA"
        assert summary.candidates[0].action == "buy"
        assert summary.candidates[0].status == "ordered"
        assert summary.candidates[0].proposed_quantity > 0
        assert "证据" in summary.candidates[0].thesis
        assert summary.orders
        assert summary.orders[0].risk_status == "approved"
        assert [item["state"] for item in summary.orders[0].state_history] == [
            "new",
            "validated",
            "risk_approved",
            "sent",
            "filled",
        ]
        assert summary.positions
        assert summary.latest_review is not None
        assert summary.latest_review.readiness == "collecting"
        assert summary.latest_review.trade_count == 0
        assert len(runs) == 1
        assert runs[0].trigger == PaperRunTrigger.manual
        assert runs[0].status == PaperRunStatus.completed
        assert runs[0].candidates_count == len(summary.candidates)
        assert runs[0].orders_count == len(summary.orders)
        assert runs[0].review_id == summary.latest_review.id
        assert runs[0].finished_at is not None


def test_daily_run_persists_core_order_state_events_for_run():
    with make_session() as session:
        run_daily_paper_trading_loop(session, FixtureProvider())

        run = session.exec(select(PaperRun)).one()
        events = list(
            session.exec(
                select(CoreEventLog)
                .where(CoreEventLog.run_id == run.id, CoreEventLog.topic == "order_state")
                .order_by(CoreEventLog.sequence)
            ).all()
        )

        assert [json.loads(event.payload_json)["state"] for event in events] == [
            "new",
            "validated",
            "risk_approved",
            "sent",
            "filled",
        ]
        assert all(event.team_id == run.team_id for event in events)
        assert len({event.correlation_id for event in events}) == 1


def test_list_paper_run_events_returns_persisted_core_events():
    with make_session() as session:
        run_daily_paper_trading_loop(session, FixtureProvider())
        run = session.exec(select(PaperRun)).one()

        events = list_paper_run_events(session, run.id)

        assert [event.topic for event in events] == ["order_state"] * 5
        assert [json.loads(event.payload_json)["state"] for event in events] == [
            "new",
            "validated",
            "risk_approved",
            "sent",
            "filled",
        ]


def test_daily_run_is_idempotent_for_current_trading_day():
    with make_session() as session:
        provider = FixtureProvider()

        first = run_daily_paper_trading_loop(session, provider)
        second = run_daily_paper_trading_loop(session, provider)

        orders = session.exec(select(PaperOrder)).all()
        reviews = session.exec(select(PaperReview)).all()
        runs = session.exec(select(PaperRun).order_by(PaperRun.started_at)).all()
        assert len(orders) == 1
        assert len(reviews) == 1
        assert [run.status for run in runs] == [PaperRunStatus.completed, PaperRunStatus.skipped]
        assert second.account.cash == first.account.cash
        assert second.orders[0].id == first.orders[0].id


def test_scheduled_daily_run_records_scheduled_trigger():
    with make_session() as session:
        summary = run_daily_paper_trading_loop(session, FixtureProvider(), trigger=PaperRunTrigger.scheduled)
        runs = list_paper_runs(session)

        assert len(runs) == 1
        assert runs[0].trigger == "scheduled"
        assert runs[0].status == "completed"
        assert runs[0].trading_day == summary.latest_review.trading_day


def test_daily_run_marks_run_failed_when_provider_raises():
    with make_session() as session:
        with pytest.raises(RuntimeError, match="quote source failed"):
            run_daily_paper_trading_loop(session, FailingQuoteProvider())

        runs = session.exec(select(PaperRun)).all()
        assert len(runs) == 1
        assert runs[0].status == PaperRunStatus.failed
        assert "quote source failed" in runs[0].error_message
        assert runs[0].finished_at is not None


def test_buy_order_fills_and_updates_cash_and_position():
    with make_session() as session:
        provider = FixtureProvider()

        order = submit_paper_order(session, provider, PaperOrderCreate(ticker="aapl", side="buy", quantity=2))
        summary = get_paper_trading_summary(session, provider)

        assert order.status == "filled"
        assert order.fill_price == 100.0
        assert order.core_order_id is not None
        assert order.core_intent_id is not None
        assert order.risk_status == "approved"
        assert order.risk_code == "approved"
        assert [item["state"] for item in order.state_history] == [
            "new",
            "validated",
            "risk_approved",
            "sent",
            "filled",
        ]
        assert summary.account.cash == 99800.0
        assert summary.account.equity == 100000.0
        assert len(summary.positions) == 1
        assert summary.positions[0].ticker == "AAPL"
        assert summary.positions[0].quantity == 2
        assert summary.positions[0].average_cost == 100.0
        assert summary.positions[0].unrealized_pnl == 0.0


def test_sell_order_realizes_profit_and_reduces_position():
    with make_session() as session:
        provider = FixtureProvider()

        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 125.0
        order = submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))
        summary = get_paper_trading_summary(session, provider)

        assert order.status == "filled"
        assert order.realized_pnl == 25.0
        assert summary.account.cash == 99925.0
        assert summary.account.realized_pnl == 25.0
        assert summary.account.equity == 100050.0
        assert summary.positions[0].quantity == 1
        assert summary.positions[0].unrealized_pnl == 25.0


def test_order_rejects_insufficient_cash_and_oversell():
    with make_session() as session:
        provider = FixtureProvider()

        rejected_buy = submit_paper_order(session, provider, PaperOrderCreate(ticker="MSFT", side="buy", quantity=1000))
        summary = get_paper_trading_summary(session, provider)

        assert rejected_buy.status == "rejected"
        assert rejected_buy.risk_status == "rejected"
        assert rejected_buy.risk_code == "max_order_notional"
        assert "exceeds" in rejected_buy.rejection_reason
        assert summary.account.cash == 100000.0
        assert summary.positions == []

        rejected_sell = submit_paper_order(session, provider, PaperOrderCreate(ticker="NVDA", side="sell", quantity=1))

        assert rejected_sell.status == "rejected"
        assert rejected_sell.risk_status == "rejected"
        assert rejected_sell.risk_code == "insufficient_position_value"
