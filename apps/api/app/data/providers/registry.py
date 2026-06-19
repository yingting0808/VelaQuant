from typing import Protocol

from app.core.config import Settings, get_settings
from app.data.providers.base import (
    EvidenceItem,
    FundamentalSnapshot,
    MarketDataProvider,
    MarketSnapshot,
    PriceHistoryBar,
    ProviderStatus,
    Quote,
)
from app.data.providers.openbb_optional import OpenBBOptionalProvider
from app.data.providers.sec_edgar import SecEdgarProvider


class ResearchEvidenceProvider(Protocol):
    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        raise NotImplementedError

    def get_statuses(self) -> list[ProviderStatus]:
        raise NotImplementedError


class HybridMarketDataProvider:
    def __init__(
        self,
        *,
        sec_provider: ResearchEvidenceProvider | None = None,
        openbb_provider: OpenBBOptionalProvider | None = None,
    ) -> None:
        self.sec_provider = sec_provider
        self.openbb_provider = openbb_provider or OpenBBOptionalProvider()

    def get_quote(self, ticker: str) -> Quote:
        return self.openbb_provider.get_quote(ticker)

    def get_price_history(
        self,
        ticker: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        history = self.openbb_provider.get_price_history(
            ticker,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
        return history

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return self.openbb_provider.get_fundamentals(ticker)

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.strip().upper()
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=self.get_price_history(normalized),
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        if self.sec_provider is not None:
            evidence.extend(self.sec_provider.get_research_evidence(ticker))
        return evidence

    def get_statuses(self) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []
        if self.sec_provider is not None:
            statuses.extend(self.sec_provider.get_statuses())
        statuses.extend(self.openbb_provider.get_statuses())
        return statuses

    def close(self) -> None:
        if self.sec_provider is None:
            return
        close = getattr(self.sec_provider, "close", None)
        if callable(close):
            close()


def build_market_data_provider(settings: Settings | None = None) -> MarketDataProvider:
    active_settings = settings or get_settings()
    mode = active_settings.data_mode

    if mode == "mock":
        from app.data.providers.mock import MockMarketDataProvider

        return MockMarketDataProvider()

    if mode == "openbb_optional":
        return HybridMarketDataProvider(sec_provider=None, openbb_provider=OpenBBOptionalProvider())

    sec_provider = SecEdgarProvider(
        user_agent=active_settings.sec_user_agent,
        timeout_seconds=active_settings.sec_timeout_seconds,
    )

    if mode == "sec_edgar":
        return HybridMarketDataProvider(
            sec_provider=sec_provider,
            openbb_provider=OpenBBOptionalProvider(),
        )

    return HybridMarketDataProvider(sec_provider=sec_provider, openbb_provider=OpenBBOptionalProvider())
