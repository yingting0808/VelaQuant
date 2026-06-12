from app.data.providers.mock import MockMarketDataProvider


def test_mock_provider_returns_quote_with_source_metadata():
    provider = MockMarketDataProvider()

    quote = provider.get_quote("aapl")

    assert quote.ticker == "AAPL"
    assert quote.price > 0
    assert quote.source == "mock"
    assert quote.updated_at.endswith("Z")


def test_mock_provider_strips_whitespace_for_quote_lookup():
    provider = MockMarketDataProvider()

    quote = provider.get_quote(" aapl ")

    assert quote.ticker == "AAPL"
    assert quote.price == 210.12


def test_mock_provider_uses_default_price_for_normalized_unknown_ticker():
    provider = MockMarketDataProvider()

    quote = provider.get_quote(" unknown ")

    assert quote.ticker == "UNKNOWN"
    assert quote.price == 100.0


def test_mock_provider_returns_evidence_items():
    provider = MockMarketDataProvider()

    evidence = provider.get_research_evidence(" MSFT ")

    assert len(evidence) >= 2
    assert all(item.ticker == "MSFT" for item in evidence)
    assert all(item.source for item in evidence)
    assert all(item.source_url for item in evidence)
    assert all(item.observed_at for item in evidence)
    assert evidence[0].source in {"mock_filing", "mock_news", "mock_quote"}
