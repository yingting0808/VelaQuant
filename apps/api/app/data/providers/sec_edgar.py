from datetime import UTC, datetime
from typing import Any

import httpx

from app.data.providers.base import EvidenceItem, ProviderStatus, Quote


SUPPORTED_TICKER_CIKS: dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "AMZN": "0001018724",
    "META": "0001326801",
}


def normalize_cik(value: str | int) -> str:
    return str(value).strip().lstrip("0").zfill(10)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _archive_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_int = str(int(cik))
    accession_path = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_path}/{primary_document}"


class SecEdgarProvider:
    base_url = "https://data.sec.gov"

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def __enter__(self) -> "SecEdgarProvider":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def get_quote(self, ticker: str) -> Quote:
        normalized = _normalize_ticker(ticker)
        raise ValueError(f"SEC EDGAR does not provide quotes for {normalized}")

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        normalized = _normalize_ticker(ticker)
        cik = SUPPORTED_TICKER_CIKS.get(normalized)
        if cik is None:
            return []

        try:
            response = self.client.get(
                f"{self.base_url}/submissions/CIK{cik}.json",
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        try:
            payload = response.json()
        except ValueError:
            return []

        return parse_submission_evidence(normalized, cik, payload)

    def get_statuses(self) -> list[ProviderStatus]:
        return [
            ProviderStatus(
                name="SEC EDGAR",
                mode="sec_edgar",
                available=True,
                message="SEC submissions adapter is configured for the supported ticker universe.",
                checked_at=_utc_now(),
                version="data.sec.gov",
            )
        ]


def parse_submission_evidence(ticker: str, cik: str, payload: dict[str, Any]) -> list[EvidenceItem]:
    if not isinstance(payload, dict):
        return []

    filings = payload.get("filings", {})
    if not isinstance(filings, dict):
        return []

    recent = filings.get("recent", {})
    if not isinstance(recent, dict):
        return []

    accession_numbers = _list_field(recent, "accessionNumber")
    filing_dates = _list_field(recent, "filingDate")
    forms = _list_field(recent, "form")
    primary_documents = _list_field(recent, "primaryDocument")
    if (
        accession_numbers is None
        or filing_dates is None
        or forms is None
        or primary_documents is None
    ):
        return []

    observed_at = _utc_now()
    evidence: list[EvidenceItem] = []

    for index, _ in enumerate(accession_numbers[:5]):
        accession_number = _value_at(accession_numbers, index)
        form = _value_at(forms, index)
        filing_date = _value_at(filing_dates, index)
        primary_document = _value_at(primary_documents, index)
        if not accession_number or not form or not filing_date or not primary_document:
            continue

        evidence.append(
            EvidenceItem(
                ticker=ticker,
                title=f"{ticker} {form} filed",
                summary=f"{ticker} filed {form} with SEC EDGAR on {filing_date}.",
                source="sec_edgar",
                source_url=_archive_url(cik, accession_number, primary_document),
                observed_at=observed_at,
                form=form,
                filing_date=filing_date,
                accession_number=accession_number,
            )
        )

    return evidence


def _list_field(values: dict[str, Any], key: str) -> list[Any] | None:
    value = values.get(key, [])
    return value if isinstance(value, list) else None


def _value_at(values: list[Any], index: int) -> str:
    if index >= len(values):
        return ""
    value = values[index]
    return str(value).strip() if value is not None else ""
