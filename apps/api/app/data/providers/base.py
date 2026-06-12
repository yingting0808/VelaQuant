from typing import Protocol

from pydantic import BaseModel, Field


class ProviderStatus(BaseModel):
    name: str
    mode: str
    available: bool
    message: str
    checked_at: str
    version: str | None = None


class Quote(BaseModel):
    ticker: str
    price: float | None
    currency: str
    source: str
    updated_at: str
    change: float | None = None
    change_percent: float | None = None
    volume: int | None = None
    is_fallback: bool = False
    message: str = ""


class PriceHistoryBar(BaseModel):
    ticker: str
    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None
    source: str


class FundamentalSnapshot(BaseModel):
    ticker: str
    market_cap: float | None
    pe_ratio: float | None
    eps: float | None
    price_to_sales: float | None
    price_to_book: float | None
    gross_margin: float | None
    profit_margin: float | None
    operating_margin: float | None
    debt_to_equity: float | None
    source: str
    period_ending: str | None
    updated_at: str
    is_fallback: bool = False
    message: str = ""


class MarketSnapshot(BaseModel):
    ticker: str
    quote: Quote
    fundamentals: FundamentalSnapshot
    history: list[PriceHistoryBar] = Field(default_factory=list)


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

    def get_price_history(
        self,
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        raise NotImplementedError

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        raise NotImplementedError

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        raise NotImplementedError

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        raise NotImplementedError

    def get_statuses(self) -> list[ProviderStatus]:
        raise NotImplementedError
