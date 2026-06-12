from typing import Protocol

from pydantic import BaseModel


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


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str) -> Quote:
        raise NotImplementedError

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        raise NotImplementedError
