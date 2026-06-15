from app.core.config import Settings
from app.data.providers.base import EvidenceItem, ProviderStatus
from app.data.providers.mock import MockMarketDataProvider


def test_provider_status_serializes_operational_state():
    status = ProviderStatus(
        name="SEC EDGAR",
        mode="sec_edgar",
        available=True,
        message="configured",
        checked_at="2026-06-12T00:00:00Z",
        version="api",
    )

    assert status.model_dump() == {
        "name": "SEC EDGAR",
        "mode": "sec_edgar",
        "available": True,
        "message": "configured",
        "checked_at": "2026-06-12T00:00:00Z",
        "version": "api",
    }


def test_evidence_item_accepts_sec_filing_metadata():
    evidence = EvidenceItem(
        ticker="AAPL",
        title="AAPL 10-K filed",
        summary="AAPL filed a 10-K on 2025-10-31.",
        source="sec_edgar",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/example.htm",
        observed_at="2025-10-31T00:00:00Z",
        form="10-K",
        filing_date="2025-10-31",
        accession_number="0000320193-25-000079",
    )

    assert evidence.form == "10-K"
    assert evidence.filing_date == "2025-10-31"
    assert evidence.accession_number == "0000320193-25-000079"


def test_mock_provider_reports_local_status():
    status = MockMarketDataProvider().get_statuses()[0]

    assert status.name == "Mock"
    assert status.mode == "mock"
    assert status.available is True
    assert status.message
    assert status.checked_at.endswith("Z")
    assert status.version == "local"


def test_settings_expose_data_provider_defaults(monkeypatch):
    monkeypatch.delenv("AI_STOCKS_DATA_MODE", raising=False)
    monkeypatch.delenv("AI_STOCKS_SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("AI_STOCKS_SEC_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("AI_STOCKS_STRATEGY_COMMAND_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("AI_STOCKS_LEAN_BACKTEST_TIMEOUT_SECONDS", raising=False)

    settings = Settings()

    assert settings.data_mode == "hybrid"
    assert settings.sec_timeout_seconds == 3.0
    assert "VelaQuant" in settings.sec_user_agent
    assert settings.strategy_command_timeout_seconds == 2.0
    assert settings.lean_backtest_timeout_seconds == 600.0
