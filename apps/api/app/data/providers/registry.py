from app.core.config import Settings, get_settings
from app.data.providers.base import EvidenceItem, MarketDataProvider, ProviderStatus, Quote
from app.data.providers.mock import MockMarketDataProvider
from app.data.providers.openbb_optional import OpenBBOptionalProvider
from app.data.providers.sec_edgar import SecEdgarProvider


class HybridMarketDataProvider:
    def __init__(
        self,
        *,
        mock_provider: MockMarketDataProvider | None = None,
        sec_provider: object | None = None,
        openbb_provider: OpenBBOptionalProvider | None = None,
    ) -> None:
        self.mock_provider = mock_provider or MockMarketDataProvider()
        self.sec_provider = sec_provider
        self.openbb_provider = openbb_provider or OpenBBOptionalProvider()

    def get_quote(self, ticker: str) -> Quote:
        return self.mock_provider.get_quote(ticker)

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        if self.sec_provider is not None:
            evidence.extend(self.sec_provider.get_research_evidence(ticker))
        evidence.extend(self.mock_provider.get_research_evidence(ticker))
        return evidence

    def get_statuses(self) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []
        statuses.extend(self.mock_provider.get_statuses())
        if self.sec_provider is not None:
            statuses.extend(self.sec_provider.get_statuses())
        statuses.extend(self.openbb_provider.get_statuses())
        return statuses


def build_market_data_provider(settings: Settings | None = None) -> MarketDataProvider:
    active_settings = settings or get_settings()
    mode = active_settings.data_mode

    if mode == "mock":
        return MockMarketDataProvider()

    if mode == "openbb_optional":
        return OpenBBOptionalProvider()

    sec_provider = SecEdgarProvider(
        user_agent=active_settings.sec_user_agent,
        timeout_seconds=active_settings.sec_timeout_seconds,
    )

    if mode == "sec_edgar":
        return HybridMarketDataProvider(sec_provider=sec_provider, openbb_provider=OpenBBOptionalProvider())

    return HybridMarketDataProvider(sec_provider=sec_provider, openbb_provider=OpenBBOptionalProvider())
