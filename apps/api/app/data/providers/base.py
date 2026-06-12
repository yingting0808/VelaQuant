from typing import Protocol

from pydantic import BaseModel


class ProviderStatus(BaseModel):
    name: str
    mode: str
    available: bool
    message: str
    checked_at: str
    version: str | None = None


class Quote(BaseModel):
    ticker: str
    price: float
    currency: str
    source: str
    updated_at: str


class EvidenceItem(BaseModel):
    ticker: str
    title: str
    summary: str
    source: str
    source_url: str
    observed_at: str
    form: str | None = None
    filing_date: str | None = None
    accession_number: str | None = None


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str) -> Quote:
        raise NotImplementedError

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        raise NotImplementedError

    def get_statuses(self) -> list[ProviderStatus]:
        raise NotImplementedError
