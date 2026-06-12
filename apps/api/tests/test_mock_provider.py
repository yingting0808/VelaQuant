from app.data.providers.mock import MockMarketDataProvider


def test_mock_provider_returns_quote_with_source_metadata():
    provider = MockMarketDataProvider()

    quote = provider.get_quote("aapl")

    assert quote.ticker == "AAPL"
    assert quote.price > 0
    assert quote.source == "mock"
    assert quote.updated_at.endswith("Z")


def test_mock_provider_returns_evidence_items():
    provider = MockMarketDataProvider()

    evidence = provider.get_research_evidence("MSFT")

    assert len(evidence) >= 2
    assert evidence[0].ticker == "MSFT"
    assert evidence[0].source in {"mock_filing", "mock_news", "mock_quote"}
