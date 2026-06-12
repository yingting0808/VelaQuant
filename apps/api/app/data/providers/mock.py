from datetime import UTC, datetime

from app.data.providers.base import (
    EvidenceItem,
    FundamentalSnapshot,
    MarketSnapshot,
    PriceHistoryBar,
    ProviderStatus,
    Quote,
)


def _checked_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


class MockMarketDataProvider:
    def get_quote(self, ticker: str) -> Quote:
        normalized = _normalize_ticker(ticker)
        prices = {
            "AAPL": 210.12,
            "MSFT": 430.55,
            "NVDA": 125.75,
            "AMZN": 181.42,
            "META": 512.34,
        }
        return Quote(
            ticker=normalized,
            price=prices.get(normalized, 100.0),
            currency="USD",
            source="mock",
            updated_at="2026-06-12T13:30:00Z",
            change=1.25,
            change_percent=0.006,
            volume=55443322,
            is_fallback=True,
            message="Mock fallback quote for display only.",
        )

    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        normalized = _normalize_ticker(ticker)
        quote = self.get_quote(normalized)
        base_price = quote.price or 100.0
        return [
            PriceHistoryBar(
                ticker=normalized,
                date="2026-06-10",
                open=round(base_price - 2.1, 2),
                high=round(base_price + 1.8, 2),
                low=round(base_price - 3.0, 2),
                close=round(base_price - 0.9, 2),
                volume=42000000,
                source="mock",
            ),
            PriceHistoryBar(
                ticker=normalized,
                date="2026-06-11",
                open=round(base_price - 0.8, 2),
                high=round(base_price + 2.4, 2),
                low=round(base_price - 1.4, 2),
                close=round(base_price + 0.6, 2),
                volume=45500000,
                source="mock",
            ),
            PriceHistoryBar(
                ticker=normalized,
                date="2026-06-12",
                open=round(base_price + 0.5, 2),
                high=round(base_price + 2.9, 2),
                low=round(base_price - 0.7, 2),
                close=base_price,
                volume=55443322,
                source="mock",
            ),
        ]

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        normalized = _normalize_ticker(ticker)
        market_caps = {
            "AAPL": 3200000000000,
            "MSFT": 3400000000000,
            "NVDA": 3500000000000,
            "AMZN": 1900000000000,
            "META": 1300000000000,
        }
        return FundamentalSnapshot(
            ticker=normalized,
            market_cap=market_caps.get(normalized, 100000000000),
            pe_ratio=31.5,
            eps=6.42,
            price_to_sales=8.4,
            price_to_book=12.1,
            gross_margin=0.68,
            profit_margin=0.24,
            operating_margin=0.31,
            debt_to_equity=0.42,
            source="mock",
            period_ending="2026-03-31",
            updated_at="2026-06-12T00:00:00Z",
            is_fallback=True,
            message="Mock fallback fundamentals for display only.",
        )

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = _normalize_ticker(ticker)
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=self.get_price_history(normalized),
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        normalized = _normalize_ticker(ticker)
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

    def get_statuses(self) -> list[ProviderStatus]:
        return [
            ProviderStatus(
                name="Mock",
                mode="mock",
                available=True,
                message="Deterministic local fallback data is available.",
                checked_at=_checked_at(),
                version="local",
            )
        ]
