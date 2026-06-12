from app.core.config import Settings
from app.data.providers.base import EvidenceItem, ProviderStatus
from app.data.providers.openbb_optional import OpenBBOptionalProvider
from app.data.providers.registry import HybridMarketDataProvider, build_market_data_provider


class StaticEvidenceProvider:
    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                ticker=ticker.strip().upper(),
                title="AAPL 10-K filed",
                summary="AAPL filed 10-K with SEC EDGAR.",
                source="sec_edgar",
                source_url="https://www.sec.gov/example",
                observed_at="2026-06-12T00:00:00Z",
                form="10-K",
                filing_date="2025-10-31",
                accession_number="0000320193-25-000079",
            )
        ]

    def get_statuses(self) -> list[ProviderStatus]:
        return [
            ProviderStatus(
                name="SEC EDGAR",
                mode="sec_edgar",
                available=True,
                message="fixture",
                checked_at="2026-06-12T00:00:00Z",
                version="fixture",
            )
        ]


def test_hybrid_provider_uses_mock_quotes_and_sec_evidence():
    provider = HybridMarketDataProvider(sec_provider=StaticEvidenceProvider())

    quote = provider.get_quote("aapl")
    evidence = provider.get_research_evidence("aapl")
    statuses = provider.get_statuses()

    assert quote.source == "mock"
    assert evidence[0].source == "sec_edgar"
    assert any(status.name == "Mock" for status in statuses)
    assert any(status.name == "SEC EDGAR" for status in statuses)


def test_provider_registry_builds_hybrid_by_default():
    provider = build_market_data_provider(
        Settings(
            data_mode="hybrid",
            sec_user_agent="VelaQuant tests contact@example.com",
            sec_timeout_seconds=1.0,
        )
    )

    assert isinstance(provider, HybridMarketDataProvider)


def test_provider_registry_openbb_optional_uses_mock_quotes_with_openbb_status():
    provider = build_market_data_provider(Settings(data_mode="openbb_optional"))

    quote = provider.get_quote("aapl")
    statuses = provider.get_statuses()

    assert isinstance(provider, HybridMarketDataProvider)
    assert quote.source == "mock"
    assert any(status.name == "Mock" for status in statuses)
    assert any(status.name == "OpenBB" for status in statuses)


def test_openbb_optional_status_reports_missing_package():
    provider = OpenBBOptionalProvider(module_finder=lambda _: None)

    status = provider.get_statuses()[0]

    assert status.name == "OpenBB"
    assert status.mode == "openbb_optional"
    assert status.available is False
    assert status.version is None


def test_openbb_optional_status_reports_installed_package():
    provider = OpenBBOptionalProvider(module_finder=lambda _: object())

    status = provider.get_statuses()[0]

    assert status.name == "OpenBB"
    assert status.mode == "openbb_optional"
    assert status.available is True
    assert status.version == "installed"
