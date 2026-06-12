from app.data.providers.openbb_optional import OpenBBOptionalProvider


class FakeTable:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orient="records"):
        assert orient == "records"
        return self.records


class FakeOpenBBResult:
    def __init__(self, records):
        self.records = records

    def to_df(self):
        return FakeTable(self.records)


class FakePriceApi:
    def quote(self, symbol: str, provider: str):
        assert provider == "yfinance"
        return FakeOpenBBResult(
            [
                {
                    "symbol": symbol,
                    "last_price": 211.25,
                    "currency": "USD",
                    "change": 1.13,
                    "change_percent": 0.54,
                    "volume": 55443322,
                }
            ]
        )

    def historical(self, symbol: str, provider: str, interval: str, start_date=None, end_date=None):
        assert provider == "yfinance"
        assert interval == "1d"
        return FakeOpenBBResult(
            [
                {"date": "2026-06-10", "open": 208.0, "high": 212.0, "low": 207.0, "close": 211.0, "volume": 1000},
                {"date": "2026-06-11", "open": 211.0, "high": 214.0, "low": 210.0, "close": 213.0, "volume": 2000},
            ]
        )


class FakeFundamentalApi:
    def metrics(self, symbol: str, provider: str):
        assert provider == "yfinance"
        return FakeOpenBBResult(
            [
                {
                    "symbol": symbol,
                    "market_cap": 3100000000000,
                    "pe_ratio": 30.2,
                    "eps": 6.91,
                    "price_to_sales": 8.5,
                    "price_to_book": 14.2,
                    "gross_margin": 0.46,
                    "profit_margin": 0.25,
                    "operating_margin": 0.32,
                    "debt_to_equity": 1.2,
                    "period_ending": "2026-03-31",
                }
            ]
        )


class FakeEquityApi:
    price = FakePriceApi()
    fundamental = FakeFundamentalApi()


class FakeOpenBBClient:
    equity = FakeEquityApi()


class RaisingPriceApi:
    def quote(self, symbol: str, provider: str):
        raise RuntimeError("provider unavailable")

    def historical(self, symbol: str, provider: str, interval: str, start_date=None, end_date=None):
        raise RuntimeError("history unavailable")


class RaisingFundamentalApi:
    def metrics(self, symbol: str, provider: str):
        raise RuntimeError("fundamentals unavailable")


class RaisingEquityApi:
    price = RaisingPriceApi()
    fundamental = RaisingFundamentalApi()


class RaisingOpenBBClient:
    equity = RaisingEquityApi()


def test_openbb_provider_reports_missing_package_without_client():
    provider = OpenBBOptionalProvider(module_finder=lambda _: None)

    status = provider.get_statuses()[0]
    quote = provider.get_quote("AAPL")

    assert status.available is False
    assert quote.price is None
    assert quote.source == "openbb_yfinance"
    assert quote.is_fallback is False
    assert "not installed" in quote.message


def test_openbb_provider_parses_quote_history_and_fundamentals():
    provider = OpenBBOptionalProvider(openbb_client=FakeOpenBBClient())

    quote = provider.get_quote(" aapl ")
    history = provider.get_price_history("aapl", interval="1d")
    fundamentals = provider.get_fundamentals("aapl")

    assert quote.ticker == "AAPL"
    assert quote.price == 211.25
    assert quote.volume == 55443322
    assert quote.source == "openbb_yfinance"
    assert history[0].close == 211.0
    assert fundamentals.market_cap == 3100000000000
    assert fundamentals.pe_ratio == 30.2


def test_openbb_provider_returns_unavailable_payloads_when_client_raises():
    provider = OpenBBOptionalProvider(openbb_client=RaisingOpenBBClient())

    quote = provider.get_quote("MSFT")
    history = provider.get_price_history("MSFT")
    fundamentals = provider.get_fundamentals("MSFT")

    assert quote.price is None
    assert "provider unavailable" in quote.message
    assert history == []
    assert "fundamentals unavailable" in fundamentals.message
