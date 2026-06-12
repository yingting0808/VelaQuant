from app.data.providers.base import FundamentalSnapshot, MarketSnapshot, PriceHistoryBar, Quote
from app.data.providers.mock import MockMarketDataProvider


def test_quote_accepts_market_data_fields():
    quote = Quote(
        ticker="AAPL",
        price=210.12,
        currency="USD",
        source="openbb_yfinance",
        updated_at="2026-06-12T13:30:00Z",
        change=1.25,
        change_percent=0.006,
        volume=55443322,
        is_fallback=False,
        message="OpenBB quote loaded.",
    )

    assert quote.model_dump() == {
        "ticker": "AAPL",
        "price": 210.12,
        "currency": "USD",
        "source": "openbb_yfinance",
        "updated_at": "2026-06-12T13:30:00Z",
        "change": 1.25,
        "change_percent": 0.006,
        "volume": 55443322,
        "is_fallback": False,
        "message": "OpenBB quote loaded.",
    }


def test_price_history_bar_serializes_ohlcv():
    bar = PriceHistoryBar(
        ticker="MSFT",
        date="2026-06-10",
        open=430.0,
        high=435.5,
        low=428.2,
        close=434.1,
        volume=22334455,
        source="openbb_yfinance",
    )

    assert bar.close == 434.1
    assert bar.source == "openbb_yfinance"


def test_fundamental_snapshot_accepts_missing_metrics():
    snapshot = FundamentalSnapshot(
        ticker="NVDA",
        market_cap=3500000000000,
        pe_ratio=None,
        eps=2.45,
        price_to_sales=None,
        price_to_book=None,
        gross_margin=0.74,
        profit_margin=None,
        operating_margin=None,
        debt_to_equity=None,
        source="openbb_yfinance",
        period_ending=None,
        updated_at="2026-06-12T00:00:00Z",
        is_fallback=False,
        message="Fundamentals loaded.",
    )

    assert snapshot.pe_ratio is None
    assert snapshot.market_cap == 3500000000000


def test_mock_provider_returns_market_snapshot_with_fallback_labels():
    provider = MockMarketDataProvider()

    snapshot = provider.get_market_snapshot(" meta ")

    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.ticker == "META"
    assert snapshot.quote.source == "mock"
    assert snapshot.quote.is_fallback is True
    assert snapshot.fundamentals.source == "mock"
    assert snapshot.fundamentals.is_fallback is True
    assert len(snapshot.history) >= 3
