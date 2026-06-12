import httpx

from app.data.providers.sec_edgar import (
    SUPPORTED_TICKER_CIKS,
    SecEdgarProvider,
    normalize_cik,
)


SEC_SUBMISSIONS_FIXTURE = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": ["0000320193-25-000079", "0000320193-25-000050"],
            "filingDate": ["2025-10-31", "2025-08-01"],
            "reportDate": ["2025-09-27", "2025-06-28"],
            "form": ["10-K", "10-Q"],
            "primaryDocument": ["aapl-20250927.htm", "aapl-20250628.htm"],
        }
    },
}


def test_normalize_cik_pads_to_ten_digits():
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik(789019) == "0000789019"


def test_supported_ticker_map_contains_initial_universe():
    assert SUPPORTED_TICKER_CIKS["AAPL"] == "0000320193"
    assert SUPPORTED_TICKER_CIKS["MSFT"] == "0000789019"
    assert SUPPORTED_TICKER_CIKS["NVDA"] == "0001045810"
    assert SUPPORTED_TICKER_CIKS["AMZN"] == "0001018724"
    assert SUPPORTED_TICKER_CIKS["META"] == "0001326801"


def test_sec_provider_parses_recent_filings_into_evidence_items():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/submissions/CIK0000320193.json"
        assert request.headers["User-Agent"] == "VelaQuant tests contact@example.com"
        return httpx.Response(200, json=SEC_SUBMISSIONS_FIXTURE)

    provider = SecEdgarProvider(
        user_agent="VelaQuant tests contact@example.com",
        timeout_seconds=1.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    evidence = provider.get_research_evidence(" aapl ")

    assert len(evidence) == 2
    assert evidence[0].ticker == "AAPL"
    assert evidence[0].source == "sec_edgar"
    assert evidence[0].form == "10-K"
    assert evidence[0].filing_date == "2025-10-31"
    assert evidence[0].accession_number == "0000320193-25-000079"
    assert "AAPL filed 10-K" in evidence[0].summary
    assert (
        evidence[0].source_url
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
    )


def test_sec_provider_reports_unsupported_ticker_without_network_call():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    provider = SecEdgarProvider(
        user_agent="VelaQuant tests contact@example.com",
        timeout_seconds=1.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.get_research_evidence("ZZZZ") == []
    status = provider.get_statuses()[0]
    assert status.available is True
    assert status.name == "SEC EDGAR"
    assert called is False


def test_sec_provider_returns_no_evidence_when_request_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    provider = SecEdgarProvider(
        user_agent="VelaQuant tests contact@example.com",
        timeout_seconds=1.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.get_research_evidence("AAPL") == []


def test_sec_provider_returns_no_evidence_for_invalid_json_or_malformed_payload():
    responses = [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"filings": []}),
        httpx.Response(200, json={"filings": {"recent": []}}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    provider = SecEdgarProvider(
        user_agent="VelaQuant tests contact@example.com",
        timeout_seconds=1.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.get_research_evidence("AAPL") == []
    assert provider.get_research_evidence("AAPL") == []
    assert provider.get_research_evidence("AAPL") == []


def test_sec_provider_context_manager_closes_only_owned_clients():
    with SecEdgarProvider(
        user_agent="VelaQuant tests contact@example.com",
        timeout_seconds=1.0,
    ) as owned_provider:
        owned_client = owned_provider.client
        assert owned_client.is_closed is False

    assert owned_client.is_closed is True

    injected_client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))

    with SecEdgarProvider(
        user_agent="VelaQuant tests contact@example.com",
        timeout_seconds=1.0,
        client=injected_client,
    ):
        assert injected_client.is_closed is False

    assert injected_client.is_closed is False
    injected_client.close()
