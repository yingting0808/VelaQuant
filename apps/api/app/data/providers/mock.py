from app.data.providers.base import EvidenceItem, Quote


class MockMarketDataProvider:
    def get_quote(self, ticker: str) -> Quote:
        normalized = ticker.upper()
        prices = {"AAPL": 210.12, "MSFT": 430.55, "NVDA": 125.75}
        return Quote(
            ticker=normalized,
            price=prices.get(normalized, 100.0),
            currency="USD",
            source="mock",
            updated_at="2026-06-12T13:30:00Z",
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        normalized = ticker.upper()
        return [
            EvidenceItem(
                ticker=normalized,
                title=f"{normalized} latest filing snapshot",
                summary="Revenue growth remains positive while operating expense growth requires monitoring.",
                source="mock_filing",
                source_url=f"https://example.local/filings/{normalized}",
                observed_at="2026-06-12T13:00:00Z",
            ),
            EvidenceItem(
                ticker=normalized,
                title=f"{normalized} market news",
                summary="Recent market coverage highlights demand resilience and valuation sensitivity.",
                source="mock_news",
                source_url=f"https://example.local/news/{normalized}",
                observed_at="2026-06-12T13:10:00Z",
            ),
        ]
