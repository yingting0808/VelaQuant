from sqlmodel import Session, SQLModel, create_engine

from app.data.providers.base import FundamentalSnapshot, MarketDataProvider, PriceHistoryBar, ProviderStatus, Quote
from app.services.workspace import (
    NoteCreate,
    PositionUpsert,
    WatchlistUpsert,
    create_note,
    delete_position,
    delete_watchlist_item,
    get_or_create_default_workspace,
    get_portfolio_payload,
    get_workspace_summary,
    import_positions_csv,
    list_notes,
    list_watchlist_items,
    upsert_position,
    upsert_watchlist_item,
)


class FixtureProvider(MarketDataProvider):
    def get_quote(self, ticker: str) -> Quote:
        prices = {"AAPL": 210.12, "MSFT": 430.55, "NVDA": 125.75, "TSLA": None}
        return Quote(
            ticker=ticker,
            price=prices.get(ticker, 100.0),
            currency="USD",
            source="fixture",
            updated_at="2026-06-13T00:00:00Z",
            change=None,
            change_percent=None,
            volume=None,
            is_fallback=False,
            message="fixture quote",
        )

    def get_price_history(self, ticker: str, start_date=None, end_date=None, interval="1d") -> list[PriceHistoryBar]:
        return []

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker,
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
            is_fallback=False,
            message="fixture fundamentals",
        )

    def get_research_evidence(self, ticker: str) -> list:
        return []

    def get_statuses(self) -> list[ProviderStatus]:
        return []


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_default_workspace_bootstraps_portfolio_and_watchlist():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        summary = get_workspace_summary(session)

        assert workspace.team.name == "个人工作区"
        assert workspace.portfolio.name == "主组合"
        assert summary.team_name == "个人工作区"
        assert summary.portfolio_name == "主组合"
        assert summary.position_count == 2
        assert summary.watchlist_count == 3


def test_portfolio_payload_uses_provider_prices_and_exposure_weights():
    with make_session() as session:
        portfolio = get_portfolio_payload(session, FixtureProvider())

        assert portfolio.name == "主组合"
        assert portfolio.total_market_value > 0
        assert [position.ticker for position in portfolio.positions] == ["AAPL", "MSFT"]
        assert portfolio.positions[0].price == 210.12
        assert round(sum(position.weight for position in portfolio.positions), 6) == 1.0


def test_upsert_position_updates_existing_ticker():
    with make_session() as session:
        first = upsert_position(
            session,
            PositionUpsert(ticker=" tsla ", quantity=3, average_cost=180.5, currency="usd"),
        )
        second = upsert_position(
            session,
            PositionUpsert(ticker="TSLA", quantity=4, average_cost=181.25, currency="USD"),
        )
        portfolio = get_portfolio_payload(session, FixtureProvider())

        assert first.ticker == "TSLA"
        assert second.id == first.id
        assert [position for position in portfolio.positions if position.ticker == "TSLA"][0].quantity == 4


def test_delete_position_removes_ticker_and_rejects_missing():
    with make_session() as session:
        upsert_position(session, PositionUpsert(ticker="TSLA", quantity=3, average_cost=180.5))

        deleted = delete_position(session, "tsla")

        assert deleted.ticker == "TSLA"
        try:
            delete_position(session, "tsla")
        except ValueError as error:
            assert "Unknown position ticker" in str(error)
        else:
            raise AssertionError("expected ValueError")


def test_import_positions_csv_persists_valid_rows_and_returns_errors():
    with make_session() as session:
        result = import_positions_csv(
            session,
            "ticker,quantity,average_cost,currency\nTSLA,2,190,USD\n,1,10,USD\nNVDA,5,100,USD\n",
        )
        portfolio = get_portfolio_payload(session, FixtureProvider())

        assert result.imported_count == 2
        assert result.errors[0]["field"] == "ticker"
        assert any(position.ticker == "TSLA" for position in portfolio.positions)
        assert any(position.ticker == "NVDA" for position in portfolio.positions)


def test_watchlist_upsert_and_delete():
    with make_session() as session:
        item = upsert_watchlist_item(session, WatchlistUpsert(ticker="tsla", thesis="机器人和电动车弹性"))
        updated = upsert_watchlist_item(session, WatchlistUpsert(ticker="TSLA", thesis="估值敏感"))
        items = list_watchlist_items(session)

        assert item.ticker == "TSLA"
        assert updated.id == item.id
        assert [entry for entry in items if entry.ticker == "TSLA"][0].thesis == "估值敏感"
        deleted = delete_watchlist_item(session, "TSLA")
        assert deleted.ticker == "TSLA"


def test_create_and_list_notes():
    with make_session() as session:
        note = create_note(
            session,
            NoteCreate(ticker="aapl", title="服务收入", body="观察服务业务利润率和监管风险。"),
        )
        notes = list_notes(session)

        assert note.ticker == "AAPL"
        assert notes[0].title == "服务收入"
        assert notes[0].body == "观察服务业务利润率和监管风险。"
