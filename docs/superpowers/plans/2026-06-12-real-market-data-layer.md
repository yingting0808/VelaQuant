# Real Market Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add normalized OpenBB-backed quote, history, and fundamentals data with safe fallback behavior and a Watchlist market-data UI.

**Architecture:** Extend the existing provider boundary instead of calling OpenBB from routes or components. OpenBB remains optional and injectable; route handlers consume normalized provider methods, while the frontend consumes stable MVP market endpoints with local fallback payloads.

**Tech Stack:** FastAPI, Pydantic, pytest, optional OpenBB Python SDK, yfinance provider through OpenBB, Next.js App Router, React, TypeScript, Playwright.

---

## Execution Notes

- Worktree: `D:\Documents\AI美股\.worktrees\codex-mvp-foundation`
- Branch: `codex/mvp-foundation`
- Design spec: `docs/superpowers/specs/2026-06-12-real-market-data-layer-design.md`
- Do not add broker connections, order placement, AI-triggered execution, paid data keys, streaming feeds, or real LEAN backtest execution.
- Keep OpenBB optional. Automated tests must not require OpenBB to be installed and must not make live network calls.
- Default symbols: AAPL, MSFT, NVDA, AMZN, META.
- User-entered ticker symbols should be trimmed and uppercased.
- Dashboard/watchlist display may use explicit mock fallback. AI research evidence must not use mock market data as real evidence.

## File Structure

- Modify `apps/api/app/data/providers/base.py`: normalized quote/history/fundamentals/snapshot contracts and provider protocol methods.
- Modify `apps/api/app/data/providers/mock.py`: deterministic display fallback for quote/history/fundamentals.
- Modify `apps/api/app/data/providers/openbb_optional.py`: optional OpenBB adapter with injectable client and safe unavailable payloads.
- Modify `apps/api/app/data/providers/registry.py`: route quote/history/fundamentals through OpenBB when available and mock fallback for display.
- Modify `apps/api/app/api/routes/mvp.py`: market quote/history/fundamentals/snapshot endpoints.
- Create `apps/api/tests/test_market_data_contracts.py`: contracts and mock fallback tests.
- Modify `apps/api/tests/test_provider_registry.py`: OpenBB market-data registry behavior.
- Create `apps/api/tests/test_openbb_optional_provider.py`: OpenBB parsing and failure tests.
- Modify `apps/api/tests/test_mvp_routes.py`: market endpoint tests.
- Modify `apps/web/src/lib/client-api.ts`: market payload types and fetch helpers.
- Create `apps/web/src/components/market-snapshot-panel.tsx`: client ticker lookup panel.
- Modify `apps/web/src/app/watchlist/page.tsx`: render module view and market panel.
- Modify `apps/web/src/app/styles.css`: compact market data styles.
- Modify `apps/web/tests/mvp.spec.ts`: watchlist market-data E2E coverage.

---

### Task 1: Market Data Contracts and Mock Fallback

**Files:**
- Modify: `apps/api/app/data/providers/base.py`
- Modify: `apps/api/app/data/providers/mock.py`
- Test: `apps/api/tests/test_market_data_contracts.py`
- Test: `apps/api/tests/test_mock_provider.py`

- [ ] **Step 1: Write failing contract tests**

Create `apps/api/tests/test_market_data_contracts.py`:

```python
from app.data.providers.base import FundamentalSnapshot, MarketSnapshot, PriceHistoryBar, Quote
from app.data.providers.mock import MockMarketDataProvider


def test_quote_accepts_market_data_fields():
    quote = Quote(
        ticker="AAPL",
        price=210.12,
        currency="USD",
        source="openbb_yfinance",
        updated_at="2026-06-12T13:30:00Z",
        change=1.25,
        change_percent=0.006,
        volume=55443322,
        is_fallback=False,
        message="OpenBB quote loaded.",
    )

    assert quote.model_dump() == {
        "ticker": "AAPL",
        "price": 210.12,
        "currency": "USD",
        "source": "openbb_yfinance",
        "updated_at": "2026-06-12T13:30:00Z",
        "change": 1.25,
        "change_percent": 0.006,
        "volume": 55443322,
        "is_fallback": False,
        "message": "OpenBB quote loaded.",
    }


def test_price_history_bar_serializes_ohlcv():
    bar = PriceHistoryBar(
        ticker="MSFT",
        date="2026-06-10",
        open=430.0,
        high=435.5,
        low=428.2,
        close=434.1,
        volume=22334455,
        source="openbb_yfinance",
    )

    assert bar.close == 434.1
    assert bar.source == "openbb_yfinance"


def test_fundamental_snapshot_accepts_missing_metrics():
    snapshot = FundamentalSnapshot(
        ticker="NVDA",
        market_cap=3500000000000,
        pe_ratio=None,
        eps=2.45,
        price_to_sales=None,
        price_to_book=None,
        gross_margin=0.74,
        profit_margin=None,
        operating_margin=None,
        debt_to_equity=None,
        source="openbb_yfinance",
        period_ending=None,
        updated_at="2026-06-12T00:00:00Z",
        is_fallback=False,
        message="Fundamentals loaded.",
    )

    assert snapshot.pe_ratio is None
    assert snapshot.market_cap == 3500000000000


def test_mock_provider_returns_market_snapshot_with_fallback_labels():
    provider = MockMarketDataProvider()

    snapshot = provider.get_market_snapshot(" meta ")

    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.ticker == "META"
    assert snapshot.quote.source == "mock"
    assert snapshot.quote.is_fallback is True
    assert snapshot.fundamentals.source == "mock"
    assert snapshot.fundamentals.is_fallback is True
    assert len(snapshot.history) >= 3
```

- [ ] **Step 2: Run contract tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_market_data_contracts.py -v
```

Expected: FAIL because `PriceHistoryBar`, `FundamentalSnapshot`, and `MarketSnapshot` do not exist, and the mock provider has no market snapshot methods.

- [ ] **Step 3: Extend provider contracts**

Update `apps/api/app/data/providers/base.py` so it includes these models and protocol methods:

```python
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
    history: list[PriceHistoryBar] = []


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
        *,
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
```

- [ ] **Step 4: Add mock market-data fallback**

Update `apps/api/app/data/providers/mock.py` to import the new models and add deterministic methods:

```python
from datetime import UTC, datetime

from app.data.providers.base import EvidenceItem, FundamentalSnapshot, MarketSnapshot, PriceHistoryBar, ProviderStatus, Quote


def _checked_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


class MockMarketDataProvider:
    def get_quote(self, ticker: str) -> Quote:
        normalized = _normalize_ticker(ticker)
        prices = {"AAPL": 210.12, "MSFT": 430.55, "NVDA": 125.75, "AMZN": 182.4, "META": 503.8}
        return Quote(
            ticker=normalized,
            price=prices.get(normalized, 100.0),
            currency="USD",
            source="mock",
            updated_at="2026-06-12T13:30:00Z",
            change=1.12,
            change_percent=0.005,
            volume=12345678,
            is_fallback=True,
            message="本地 Mock fallback 数据，仅用于离线展示。",
        )

    def get_price_history(
        self,
        ticker: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        normalized = _normalize_ticker(ticker)
        return [
            PriceHistoryBar(ticker=normalized, date="2026-06-10", open=98.0, high=101.0, low=97.5, close=100.0, volume=1000000, source="mock"),
            PriceHistoryBar(ticker=normalized, date="2026-06-11", open=100.0, high=103.0, low=99.0, close=102.0, volume=1200000, source="mock"),
            PriceHistoryBar(ticker=normalized, date="2026-06-12", open=102.0, high=104.5, low=101.0, close=103.5, volume=1300000, source="mock"),
        ]

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        normalized = _normalize_ticker(ticker)
        return FundamentalSnapshot(
            ticker=normalized,
            market_cap=2500000000000,
            pe_ratio=32.5,
            eps=6.42,
            price_to_sales=8.2,
            price_to_book=12.4,
            gross_margin=0.45,
            profit_margin=0.24,
            operating_margin=0.31,
            debt_to_equity=1.1,
            source="mock",
            period_ending="2026-03-31",
            updated_at="2026-06-12T13:30:00Z",
            is_fallback=True,
            message="本地 Mock fallback 基本面，仅用于离线展示。",
        )

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = _normalize_ticker(ticker)
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=self.get_price_history(normalized),
        )

    # keep existing get_research_evidence and get_statuses methods
```

Keep the existing `get_research_evidence()` and `get_statuses()` behavior. If the file already contains these methods, merge the code instead of deleting them.

- [ ] **Step 5: Run contract and mock tests**

Run:

```powershell
python -m pytest tests/test_market_data_contracts.py tests/test_mock_provider.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/api/app/data/providers/base.py apps/api/app/data/providers/mock.py apps/api/tests/test_market_data_contracts.py apps/api/tests/test_mock_provider.py
git commit -m "feat(api): add market data contracts"
```

---

### Task 2: OpenBB Optional Market Adapter

**Files:**
- Modify: `apps/api/app/data/providers/openbb_optional.py`
- Test: `apps/api/tests/test_openbb_optional_provider.py`

- [ ] **Step 1: Write failing OpenBB adapter tests**

Create `apps/api/tests/test_openbb_optional_provider.py`:

```python
from app.data.providers.openbb_optional import OpenBBOptionalProvider


class FakeTable:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orient="records"):
        assert orient == "records"
        return self.records


class FakeOpenBBResult:
    def __init__(self, records):
        self.records = records

    def to_df(self):
        return FakeTable(self.records)


class FakePriceApi:
    def quote(self, symbol: str, provider: str):
        assert provider == "yfinance"
        return FakeOpenBBResult(
            [
                {
                    "symbol": symbol,
                    "last_price": 211.25,
                    "currency": "USD",
                    "change": 1.13,
                    "change_percent": 0.54,
                    "volume": 55443322,
                }
            ]
        )

    def historical(self, symbol: str, provider: str, interval: str, start_date=None, end_date=None):
        assert provider == "yfinance"
        assert interval == "1d"
        return FakeOpenBBResult(
            [
                {"date": "2026-06-10", "open": 208.0, "high": 212.0, "low": 207.0, "close": 211.0, "volume": 1000},
                {"date": "2026-06-11", "open": 211.0, "high": 214.0, "low": 210.0, "close": 213.0, "volume": 2000},
            ]
        )


class FakeFundamentalApi:
    def metrics(self, symbol: str, provider: str):
        assert provider == "yfinance"
        return FakeOpenBBResult(
            [
                {
                    "symbol": symbol,
                    "market_cap": 3100000000000,
                    "pe_ratio": 30.2,
                    "eps": 6.91,
                    "price_to_sales": 8.5,
                    "price_to_book": 14.2,
                    "gross_margin": 0.46,
                    "profit_margin": 0.25,
                    "operating_margin": 0.32,
                    "debt_to_equity": 1.2,
                    "period_ending": "2026-03-31",
                }
            ]
        )


class FakeEquityApi:
    price = FakePriceApi()
    fundamental = FakeFundamentalApi()


class FakeOpenBBClient:
    equity = FakeEquityApi()


class RaisingPriceApi:
    def quote(self, symbol: str, provider: str):
        raise RuntimeError("provider unavailable")

    def historical(self, symbol: str, provider: str, interval: str, start_date=None, end_date=None):
        raise RuntimeError("history unavailable")


class RaisingFundamentalApi:
    def metrics(self, symbol: str, provider: str):
        raise RuntimeError("fundamentals unavailable")


class RaisingEquityApi:
    price = RaisingPriceApi()
    fundamental = RaisingFundamentalApi()


class RaisingOpenBBClient:
    equity = RaisingEquityApi()


def test_openbb_provider_reports_missing_package_without_client():
    provider = OpenBBOptionalProvider(module_finder=lambda _: None)

    status = provider.get_statuses()[0]
    quote = provider.get_quote("AAPL")

    assert status.available is False
    assert quote.price is None
    assert quote.source == "openbb_yfinance"
    assert quote.is_fallback is False
    assert "not installed" in quote.message


def test_openbb_provider_parses_quote_history_and_fundamentals():
    provider = OpenBBOptionalProvider(openbb_client=FakeOpenBBClient())

    quote = provider.get_quote(" aapl ")
    history = provider.get_price_history("aapl", interval="1d")
    fundamentals = provider.get_fundamentals("aapl")

    assert quote.ticker == "AAPL"
    assert quote.price == 211.25
    assert quote.volume == 55443322
    assert quote.source == "openbb_yfinance"
    assert history[0].close == 211.0
    assert fundamentals.market_cap == 3100000000000
    assert fundamentals.pe_ratio == 30.2


def test_openbb_provider_returns_unavailable_payloads_when_client_raises():
    provider = OpenBBOptionalProvider(openbb_client=RaisingOpenBBClient())

    quote = provider.get_quote("MSFT")
    history = provider.get_price_history("MSFT")
    fundamentals = provider.get_fundamentals("MSFT")

    assert quote.price is None
    assert "provider unavailable" in quote.message
    assert history == []
    assert "fundamentals unavailable" in fundamentals.message
```

- [ ] **Step 2: Run OpenBB adapter tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_openbb_optional_provider.py -v
```

Expected: FAIL because `OpenBBOptionalProvider` does not accept `openbb_client` and does not implement quote/history/fundamentals payloads.

- [ ] **Step 3: Implement optional OpenBB adapter**

Update `apps/api/app/data/providers/openbb_optional.py` with an injectable client and safe converters. Preserve package status behavior:

```python
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import import_module
from importlib.util import find_spec
from typing import Any

from app.data.providers.base import EvidenceItem, FundamentalSnapshot, PriceHistoryBar, ProviderStatus, Quote


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _records_from_result(result: Any) -> list[dict[str, Any]]:
    data = result
    if hasattr(data, "to_df"):
        data = data.to_df()
    elif hasattr(data, "to_dataframe"):
        data = data.to_dataframe()

    if hasattr(data, "to_dict"):
        try:
            records = data.to_dict("records")
        except TypeError:
            records = data.to_dict()
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
        if isinstance(records, dict):
            return [records]

    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]
    if isinstance(data, dict):
        return [data]
    return []


class OpenBBOptionalProvider:
    def __init__(
        self,
        module_finder: Callable[[str], object | None] = find_spec,
        openbb_client: object | None = None,
    ) -> None:
        self._client = openbb_client
        self.available = openbb_client is not None or module_finder("openbb") is not None

    @property
    def client(self) -> object | None:
        if self._client is not None:
            return self._client
        if not self.available:
            return None
        module = import_module("openbb")
        self._client = getattr(module, "obb", None)
        return self._client

    def get_quote(self, ticker: str) -> Quote:
        normalized = _normalize_ticker(ticker)
        client = self.client
        if client is None:
            return self._unavailable_quote(normalized, "OpenBB package is not installed.")
        try:
            result = client.equity.price.quote(symbol=normalized, provider="yfinance")
            record = _records_from_result(result)[0]
        except (IndexError, AttributeError, RuntimeError, ValueError, TypeError) as error:
            return self._unavailable_quote(normalized, str(error))

        return Quote(
            ticker=normalized,
            price=_number(record.get("last_price") or record.get("price") or record.get("close")),
            currency=str(record.get("currency") or "USD"),
            source="openbb_yfinance",
            updated_at=_utc_now(),
            change=_number(record.get("change")),
            change_percent=_number(record.get("change_percent")),
            volume=_integer(record.get("volume")),
            is_fallback=False,
            message="OpenBB yfinance quote loaded.",
        )

    def get_price_history(
        self,
        ticker: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> list[PriceHistoryBar]:
        normalized = _normalize_ticker(ticker)
        client = self.client
        if client is None:
            return []
        try:
            result = client.equity.price.historical(
                symbol=normalized,
                provider="yfinance",
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )
        except (AttributeError, RuntimeError, ValueError, TypeError):
            return []

        bars: list[PriceHistoryBar] = []
        for record in _records_from_result(result):
            bars.append(
                PriceHistoryBar(
                    ticker=normalized,
                    date=str(record.get("date") or record.get("datetime") or ""),
                    open=_number(record.get("open")),
                    high=_number(record.get("high")),
                    low=_number(record.get("low")),
                    close=_number(record.get("close")),
                    volume=_integer(record.get("volume")),
                    source="openbb_yfinance",
                )
            )
        return [bar for bar in bars if bar.date]

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        normalized = _normalize_ticker(ticker)
        client = self.client
        if client is None:
            return self._unavailable_fundamentals(normalized, "OpenBB package is not installed.")
        try:
            result = client.equity.fundamental.metrics(symbol=normalized, provider="yfinance")
            record = _records_from_result(result)[0]
        except (IndexError, AttributeError, RuntimeError, ValueError, TypeError) as error:
            return self._unavailable_fundamentals(normalized, str(error))

        return FundamentalSnapshot(
            ticker=normalized,
            market_cap=_number(record.get("market_cap")),
            pe_ratio=_number(record.get("pe_ratio") or record.get("trailing_pe")),
            eps=_number(record.get("eps") or record.get("eps_ttm")),
            price_to_sales=_number(record.get("price_to_sales")),
            price_to_book=_number(record.get("price_to_book")),
            gross_margin=_number(record.get("gross_margin")),
            profit_margin=_number(record.get("profit_margin")),
            operating_margin=_number(record.get("operating_margin")),
            debt_to_equity=_number(record.get("debt_to_equity")),
            source="openbb_yfinance",
            period_ending=str(record.get("period_ending")) if record.get("period_ending") else None,
            updated_at=_utc_now(),
            is_fallback=False,
            message="OpenBB yfinance fundamentals loaded.",
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        return []

    def get_statuses(self) -> list[ProviderStatus]:
        if self.available:
            return [
                ProviderStatus(
                    name="OpenBB",
                    mode="openbb_optional",
                    available=True,
                    message="OpenBB package is available for yfinance quote, history, and fundamentals.",
                    checked_at=_utc_now(),
                    version="installed",
                )
            ]
        return [
            ProviderStatus(
                name="OpenBB",
                mode="openbb_optional",
                available=False,
                message="OpenBB package is not installed.",
                checked_at=_utc_now(),
                version=None,
            )
        ]

    def _unavailable_quote(self, ticker: str, message: str) -> Quote:
        return Quote(
            ticker=ticker,
            price=None,
            currency="USD",
            source="openbb_yfinance",
            updated_at=_utc_now(),
            is_fallback=False,
            message=message,
        )

    def _unavailable_fundamentals(self, ticker: str, message: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker,
            market_cap=None,
            pe_ratio=None,
            eps=None,
            price_to_sales=None,
            price_to_book=None,
            gross_margin=None,
            profit_margin=None,
            operating_margin=None,
            debt_to_equity=None,
            source="openbb_yfinance",
            period_ending=None,
            updated_at=_utc_now(),
            is_fallback=False,
            message=message,
        )
```

- [ ] **Step 4: Run OpenBB adapter tests**

Run:

```powershell
python -m pytest tests/test_openbb_optional_provider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/api/app/data/providers/openbb_optional.py apps/api/tests/test_openbb_optional_provider.py
git commit -m "feat(api): add optional OpenBB market adapter"
```

---

### Task 3: Registry Market Fallback and MVP Market Routes

**Files:**
- Modify: `apps/api/app/data/providers/registry.py`
- Modify: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/tests/test_provider_registry.py`
- Modify: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Add failing registry tests**

Append to `apps/api/tests/test_provider_registry.py`:

```python
from app.data.providers.base import FundamentalSnapshot, PriceHistoryBar, Quote


class StaticMarketProvider:
    available = True

    def get_quote(self, ticker: str) -> Quote:
        return Quote(
            ticker=ticker.strip().upper(),
            price=333.3,
            currency="USD",
            source="openbb_yfinance",
            updated_at="2026-06-12T14:00:00Z",
            volume=999,
            is_fallback=False,
            message="fixture quote",
        )

    def get_price_history(self, ticker: str, *, start_date=None, end_date=None, interval="1d") -> list[PriceHistoryBar]:
        return [
            PriceHistoryBar(
                ticker=ticker.strip().upper(),
                date="2026-06-12",
                open=330.0,
                high=334.0,
                low=329.0,
                close=333.3,
                volume=999,
                source="openbb_yfinance",
            )
        ]

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker.strip().upper(),
            market_cap=123,
            pe_ratio=20.0,
            eps=4.2,
            price_to_sales=None,
            price_to_book=None,
            gross_margin=None,
            profit_margin=None,
            operating_margin=None,
            debt_to_equity=None,
            source="openbb_yfinance",
            period_ending=None,
            updated_at="2026-06-12T14:00:00Z",
            is_fallback=False,
            message="fixture fundamentals",
        )

    def get_statuses(self):
        return []


class UnavailableMarketProvider(StaticMarketProvider):
    available = False

    def get_quote(self, ticker: str) -> Quote:
        return Quote(
            ticker=ticker.strip().upper(),
            price=None,
            currency="USD",
            source="openbb_yfinance",
            updated_at="2026-06-12T14:00:00Z",
            is_fallback=False,
            message="OpenBB unavailable",
        )

    def get_price_history(self, ticker: str, *, start_date=None, end_date=None, interval="1d") -> list[PriceHistoryBar]:
        return []

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        return FundamentalSnapshot(
            ticker=ticker.strip().upper(),
            market_cap=None,
            pe_ratio=None,
            eps=None,
            price_to_sales=None,
            price_to_book=None,
            gross_margin=None,
            profit_margin=None,
            operating_margin=None,
            debt_to_equity=None,
            source="openbb_yfinance",
            period_ending=None,
            updated_at="2026-06-12T14:00:00Z",
            is_fallback=False,
            message="OpenBB unavailable",
        )


def test_hybrid_provider_uses_openbb_market_data_when_available():
    provider = HybridMarketDataProvider(openbb_provider=StaticMarketProvider())

    quote = provider.get_quote("aapl")
    history = provider.get_price_history("aapl")
    fundamentals = provider.get_fundamentals("aapl")

    assert quote.source == "openbb_yfinance"
    assert quote.is_fallback is False
    assert history[0].source == "openbb_yfinance"
    assert fundamentals.source == "openbb_yfinance"


def test_hybrid_provider_falls_back_to_mock_display_data_when_openbb_unavailable():
    provider = HybridMarketDataProvider(openbb_provider=UnavailableMarketProvider())

    quote = provider.get_quote("aapl")
    history = provider.get_price_history("aapl")
    fundamentals = provider.get_fundamentals("aapl")

    assert quote.source == "mock"
    assert quote.is_fallback is True
    assert history[0].source == "mock"
    assert fundamentals.source == "mock"
    assert fundamentals.is_fallback is True
```

- [ ] **Step 2: Add failing route tests**

Append to `apps/api/tests/test_mvp_routes.py`:

```python
def test_mvp_market_snapshot_route_returns_quote_fundamentals_and_sources():
    client = TestClient(create_app())

    response = client.get("/api/mvp/market/snapshot/nvda")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "NVDA"
    assert "quote" in payload
    assert "fundamentals" in payload
    assert "history" in payload
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])


def test_mvp_market_history_rejects_unsupported_interval():
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.get("/api/mvp/market/history/AAPL?interval=5m")

    assert response.status_code == 422


def test_mvp_market_quote_normalizes_arbitrary_ticker():
    client = TestClient(create_app())

    response = client.get("/api/mvp/market/quote/tsla")

    assert response.status_code == 200
    assert response.json()["ticker"] == "TSLA"
```

- [ ] **Step 3: Run registry and route tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_provider_registry.py tests/test_mvp_routes.py -v
```

Expected: FAIL because the registry lacks market methods and the market routes do not exist.

- [ ] **Step 4: Implement registry market methods**

Update `HybridMarketDataProvider` in `apps/api/app/data/providers/registry.py`:

```python
from app.data.providers.base import EvidenceItem, FundamentalSnapshot, MarketDataProvider, MarketSnapshot, PriceHistoryBar, ProviderStatus, Quote
```

Add these methods inside `HybridMarketDataProvider`:

```python
    def get_quote(self, ticker: str) -> Quote:
        quote = self.openbb_provider.get_quote(ticker)
        if quote.price is not None:
            return quote
        return self.mock_provider.get_quote(ticker)

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
        return history or self.mock_provider.get_price_history(
            ticker,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        fundamentals = self.openbb_provider.get_fundamentals(ticker)
        if fundamentals.market_cap is not None or fundamentals.pe_ratio is not None or fundamentals.eps is not None:
            return fundamentals
        return self.mock_provider.get_fundamentals(ticker)

    def get_market_snapshot(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.strip().upper()
        return MarketSnapshot(
            ticker=normalized,
            quote=self.get_quote(normalized),
            fundamentals=self.get_fundamentals(normalized),
            history=self.get_price_history(normalized),
        )
```

Keep the existing `get_research_evidence()`, `get_statuses()`, and `close()` behavior.

- [ ] **Step 5: Implement market routes**

Update `apps/api/app/api/routes/mvp.py` imports:

```python
from typing import Literal

from fastapi import APIRouter, Depends, Path
```

Add helper and routes before `@router.post("/research")`:

```python
def _normalize_path_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")
    return normalized


@router.get("/market/quote/{ticker}")
def market_quote(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    normalized = _normalize_path_ticker(ticker)
    return provider.get_quote(normalized).model_dump()


@router.get("/market/history/{ticker}")
def market_history(
    ticker: str = Path(min_length=1),
    interval: Literal["1d", "1W", "1M"] = "1d",
    start_date: str | None = None,
    end_date: str | None = None,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> list[dict]:
    normalized = _normalize_path_ticker(ticker)
    return [
        bar.model_dump()
        for bar in provider.get_price_history(
            normalized,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
    ]


@router.get("/market/fundamentals/{ticker}")
def market_fundamentals(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    normalized = _normalize_path_ticker(ticker)
    return provider.get_fundamentals(normalized).model_dump()


@router.get("/market/snapshot/{ticker}")
def market_snapshot(
    ticker: str = Path(min_length=1),
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> dict:
    settings = get_settings()
    normalized = _normalize_path_ticker(ticker)
    snapshot = provider.get_market_snapshot(normalized)
    return {
        "ticker": snapshot.ticker,
        "quote": snapshot.quote.model_dump(),
        "fundamentals": snapshot.fundamentals.model_dump(),
        "history": [bar.model_dump() for bar in snapshot.history],
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }
```

- [ ] **Step 6: Run backend route tests**

Run:

```powershell
python -m pytest tests/test_provider_registry.py tests/test_mvp_routes.py tests/test_openbb_optional_provider.py tests/test_market_data_contracts.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add apps/api/app/data/providers/registry.py apps/api/app/api/routes/mvp.py apps/api/tests/test_provider_registry.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): expose market data endpoints"
```

---

### Task 4: Frontend Market Data Client and E2E Targets

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Add failing Watchlist E2E tests**

Append to `apps/web/tests/mvp.spec.ts`:

```ts
test("watchlist renders market snapshot from API", async ({ page }) => {
  await page.route("**/api/mvp/market/snapshot/NVDA", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "NVDA",
        quote: {
          ticker: "NVDA",
          price: 125.75,
          currency: "USD",
          source: "openbb_yfinance",
          updated_at: "2026-06-12T14:00:00Z",
          change: 2.4,
          change_percent: 0.019,
          volume: 55443322,
          is_fallback: false,
          message: "OpenBB yfinance quote loaded."
        },
        fundamentals: {
          ticker: "NVDA",
          market_cap: 3500000000000,
          pe_ratio: 42.1,
          eps: 2.45,
          price_to_sales: null,
          price_to_book: null,
          gross_margin: 0.74,
          profit_margin: null,
          operating_margin: null,
          debt_to_equity: null,
          source: "openbb_yfinance",
          period_ending: "2026-03-31",
          updated_at: "2026-06-12T14:00:00Z",
          is_fallback: false,
          message: "OpenBB yfinance fundamentals loaded."
        },
        history: [
          { ticker: "NVDA", date: "2026-06-10", open: 120, high: 126, low: 119, close: 125.75, volume: 1000, source: "openbb_yfinance" }
        ],
        provider_mode: "hybrid",
        data_sources: []
      }
    });
  });

  await page.goto("/watchlist");

  await expect(page.getByRole("heading", { name: "市场快照" })).toBeVisible();
  await expect(page.getByText("NVDA", { exact: true })).toBeVisible();
  await expect(page.getByText("$125.75")).toBeVisible();
  await expect(page.getByText("openbb_yfinance")).toBeVisible();
  await expect(page.getByText("Market Cap")).toBeVisible();
  await expect(page.getByText("3.50T")).toBeVisible();
});

test("watchlist can query an arbitrary ticker and show unavailable fallback", async ({ page }) => {
  await page.route("**/api/mvp/market/snapshot/NVDA", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "NVDA",
        quote: { ticker: "NVDA", price: 125.75, currency: "USD", source: "mock", updated_at: "local", change: null, change_percent: null, volume: null, is_fallback: true, message: "本地 Mock fallback 数据，仅用于离线展示。" },
        fundamentals: { ticker: "NVDA", market_cap: null, pe_ratio: null, eps: null, price_to_sales: null, price_to_book: null, gross_margin: null, profit_margin: null, operating_margin: null, debt_to_equity: null, source: "mock", period_ending: null, updated_at: "local", is_fallback: true, message: "本地 Mock fallback 基本面，仅用于离线展示。" },
        history: [],
        provider_mode: "hybrid",
        data_sources: []
      }
    });
  });
  await page.route("**/api/mvp/market/snapshot/TSLA", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "TSLA",
        quote: { ticker: "TSLA", price: null, currency: "USD", source: "openbb_yfinance", updated_at: "local", change: null, change_percent: null, volume: null, is_fallback: false, message: "Ticker not found." },
        fundamentals: { ticker: "TSLA", market_cap: null, pe_ratio: null, eps: null, price_to_sales: null, price_to_book: null, gross_margin: null, profit_margin: null, operating_margin: null, debt_to_equity: null, source: "openbb_yfinance", period_ending: null, updated_at: "local", is_fallback: false, message: "Ticker not found." },
        history: [],
        provider_mode: "hybrid",
        data_sources: []
      }
    });
  });

  await page.goto("/watchlist");
  await page.getByLabel("Ticker").fill("tsla");
  await page.getByRole("button", { name: "查询" }).click();

  await expect(page.getByText("TSLA", { exact: true })).toBeVisible();
  await expect(page.getByText("Ticker not found.")).toBeVisible();
});
```

- [ ] **Step 2: Run E2E tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npx playwright test --grep "watchlist renders market snapshot|watchlist can query"
```

Expected: FAIL because the Watchlist market panel does not exist.

- [ ] **Step 3: Add frontend market payload types and client**

Append these types, fallback payload, validators, and helper to `apps/web/src/lib/client-api.ts`:

```ts
export type MarketQuotePayload = {
  ticker: string;
  price: number | null;
  currency: string;
  source: string;
  updated_at: string;
  change: number | null;
  change_percent: number | null;
  volume: number | null;
  is_fallback: boolean;
  message: string;
};

export type PriceHistoryBarPayload = {
  ticker: string;
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  source: string;
};

export type FundamentalSnapshotPayload = {
  ticker: string;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  price_to_sales: number | null;
  price_to_book: number | null;
  gross_margin: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  debt_to_equity: number | null;
  source: string;
  period_ending: string | null;
  updated_at: string;
  is_fallback: boolean;
  message: string;
};

export type MarketSnapshotPayload = {
  ticker: string;
  quote: MarketQuotePayload;
  fundamentals: FundamentalSnapshotPayload;
  history: PriceHistoryBarPayload[];
  provider_mode: string;
  data_sources: ProviderStatusPayload[];
};

function fallbackMarketSnapshot(ticker: string): MarketSnapshotPayload {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  return {
    ticker: normalizedTicker,
    quote: {
      ticker: normalizedTicker,
      price: null,
      currency: "USD",
      source: "offline",
      updated_at: "local",
      change: null,
      change_percent: null,
      volume: null,
      is_fallback: true,
      message: "后端 API 暂不可用，无法确认真实行情。"
    },
    fundamentals: {
      ticker: normalizedTicker,
      market_cap: null,
      pe_ratio: null,
      eps: null,
      price_to_sales: null,
      price_to_book: null,
      gross_margin: null,
      profit_margin: null,
      operating_margin: null,
      debt_to_equity: null,
      source: "offline",
      period_ending: null,
      updated_at: "local",
      is_fallback: true,
      message: "后端 API 暂不可用，无法确认基本面。"
    },
    history: [],
    provider_mode: "hybrid",
    data_sources: fallbackDataSourcesStatus.data_sources
  };
}

function isNullableNumber(value: unknown): value is number | null {
  return typeof value === "number" || value === null;
}

function isMarketQuotePayload(value: unknown): value is MarketQuotePayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isNullableNumber(value.price) &&
    typeof value.currency === "string" &&
    typeof value.source === "string" &&
    typeof value.updated_at === "string" &&
    isNullableNumber(value.change) &&
    isNullableNumber(value.change_percent) &&
    isNullableNumber(value.volume) &&
    typeof value.is_fallback === "boolean" &&
    typeof value.message === "string"
  );
}

function isPriceHistoryBarPayload(value: unknown): value is PriceHistoryBarPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.date === "string" &&
    isNullableNumber(value.open) &&
    isNullableNumber(value.high) &&
    isNullableNumber(value.low) &&
    isNullableNumber(value.close) &&
    isNullableNumber(value.volume) &&
    typeof value.source === "string"
  );
}

function isFundamentalSnapshotPayload(value: unknown): value is FundamentalSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isNullableNumber(value.market_cap) &&
    isNullableNumber(value.pe_ratio) &&
    isNullableNumber(value.eps) &&
    isNullableNumber(value.price_to_sales) &&
    isNullableNumber(value.price_to_book) &&
    isNullableNumber(value.gross_margin) &&
    isNullableNumber(value.profit_margin) &&
    isNullableNumber(value.operating_margin) &&
    isNullableNumber(value.debt_to_equity) &&
    typeof value.source === "string" &&
    (typeof value.period_ending === "string" || value.period_ending === null) &&
    typeof value.updated_at === "string" &&
    typeof value.is_fallback === "boolean" &&
    typeof value.message === "string"
  );
}

function isMarketSnapshotPayload(value: unknown): value is MarketSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isMarketQuotePayload(value.quote) &&
    isFundamentalSnapshotPayload(value.fundamentals) &&
    Array.isArray(value.history) &&
    value.history.every(isPriceHistoryBarPayload) &&
    typeof value.provider_mode === "string" &&
    Array.isArray(value.data_sources) &&
    value.data_sources.every(isProviderStatus)
  );
}

export async function getMarketSnapshot(ticker: string): Promise<MarketSnapshotPayload> {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/market/snapshot/${normalizedTicker}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackMarketSnapshot(normalizedTicker);
    }
    const payload: unknown = await response.json();
    return isMarketSnapshotPayload(payload) ? payload : fallbackMarketSnapshot(normalizedTicker);
  } catch {
    return fallbackMarketSnapshot(normalizedTicker);
  }
}
```

- [ ] **Step 4: Run TypeScript check**

Run:

```powershell
npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/web/src/lib/client-api.ts apps/web/tests/mvp.spec.ts
git commit -m "test(web): cover watchlist market snapshot"
```

---

### Task 5: Watchlist Market Snapshot UI

**Files:**
- Create: `apps/web/src/components/market-snapshot-panel.tsx`
- Modify: `apps/web/src/app/watchlist/page.tsx`
- Modify: `apps/web/src/app/styles.css`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Create market snapshot panel**

Create `apps/web/src/components/market-snapshot-panel.tsx`:

```tsx
"use client";

import { FormEvent, useEffect, useState } from "react";
import { getMarketSnapshot, type MarketSnapshotPayload } from "@/lib/client-api";

const defaultTickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META"];

function formatCurrency(value: number | null, currency: string): string {
  if (value === null) {
    return "不可用";
  }
  return new Intl.NumberFormat("en-US", {
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
    style: "currency"
  }).format(value);
}

function formatLargeNumber(value: number | null): string {
  if (value === null) {
    return "不可用";
  }
  if (Math.abs(value) >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (Math.abs(value) >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  return value.toLocaleString("en-US");
}

function formatPercent(value: number | null): string {
  return value === null ? "不可用" : `${(value * 100).toFixed(2)}%`;
}

export function MarketSnapshotPanel() {
  const [tickerInput, setTickerInput] = useState("NVDA");
  const [selectedTicker, setSelectedTicker] = useState("NVDA");
  const [snapshot, setSnapshot] = useState<MarketSnapshotPayload | null>(null);

  useEffect(() => {
    let active = true;
    getMarketSnapshot(selectedTicker).then((payload) => {
      if (active) {
        setSnapshot(payload);
      }
    });
    return () => {
      active = false;
    };
  }, [selectedTicker]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectedTicker(tickerInput.trim().toUpperCase() || "NVDA");
  }

  const quote = snapshot?.quote;
  const fundamentals = snapshot?.fundamentals;

  return (
    <section className="data-panel market-panel" aria-label="市场快照">
      <div className="panel-heading market-heading">
        <div>
          <h3>市场快照</h3>
          <p>OpenBB / yfinance 优先，离线时清楚标注 fallback</p>
        </div>
        <form className="ticker-form" onSubmit={handleSubmit}>
          <label htmlFor="ticker-query">Ticker</label>
          <input
            id="ticker-query"
            value={tickerInput}
            onChange={(event) => setTickerInput(event.target.value)}
            spellCheck={false}
          />
          <button type="submit">查询</button>
        </form>
      </div>

      <div className="ticker-strip" aria-label="默认股票">
        {defaultTickers.map((ticker) => (
          <button key={ticker} type="button" onClick={() => {
            setTickerInput(ticker);
            setSelectedTicker(ticker);
          }}>
            {ticker}
          </button>
        ))}
      </div>

      <div className="market-grid">
        <article className="market-card">
          <span className="market-label">{snapshot?.ticker ?? selectedTicker}</span>
          <strong>{formatCurrency(quote?.price ?? null, quote?.currency ?? "USD")}</strong>
          <p>{quote?.message ?? "正在加载市场数据"}</p>
          <span className={quote?.is_fallback ? "state-warn" : "state-ok"}>{quote?.source ?? "加载中"}</span>
        </article>

        <article className="market-card">
          <span className="market-label">Change</span>
          <strong>{formatPercent(quote?.change_percent ?? null)}</strong>
          <p>Volume: {quote?.volume?.toLocaleString("en-US") ?? "不可用"}</p>
        </article>

        <article className="market-card">
          <span className="market-label">Market Cap</span>
          <strong>{formatLargeNumber(fundamentals?.market_cap ?? null)}</strong>
          <p>PE: {fundamentals?.pe_ratio ?? "不可用"} · EPS: {fundamentals?.eps ?? "不可用"}</p>
        </article>
      </div>

      <div className="module-list compact-history">
        {(snapshot?.history ?? []).slice(-3).map((bar) => (
          <article className="module-row" key={`${bar.ticker}-${bar.date}`}>
            <div>
              <strong>{bar.date}</strong>
              <p>{bar.source}</p>
            </div>
            <span>{formatCurrency(bar.close, quote?.currency ?? "USD")}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Render panel on Watchlist**

Modify `apps/web/src/app/watchlist/page.tsx`:

```tsx
import { AppShell } from "@/components/app-shell";
import { MarketSnapshotPanel } from "@/components/market-snapshot-panel";
import { ModuleView } from "@/components/module-view";
import { sampleDashboard } from "@/lib/sample-data";

export default function WatchlistPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-stack">
        <ModuleView module="watchlist" />
        <MarketSnapshotPanel />
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 3: Add compact styles**

Append to `apps/web/src/app/styles.css`:

```css
.market-heading {
  align-items: flex-start;
  gap: 12px;
}

.ticker-form {
  align-items: end;
  display: grid;
  gap: 6px;
  grid-template-columns: minmax(86px, 120px) auto;
}

.ticker-form label {
  color: #667085;
  font-size: 0.78rem;
  font-weight: 700;
  grid-column: 1 / -1;
}

.ticker-form input {
  border: 1px solid #d7dee8;
  border-radius: 7px;
  min-height: 34px;
  padding: 6px 8px;
  text-transform: uppercase;
}

.ticker-form button,
.ticker-strip button {
  background: #182235;
  border: 1px solid #182235;
  border-radius: 7px;
  color: #ffffff;
  cursor: pointer;
  min-height: 34px;
  padding: 6px 10px;
}

.ticker-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px 0;
}

.market-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 14px 16px;
}

.market-card {
  border: 1px solid #e5eaf0;
  border-radius: 8px;
  display: grid;
  gap: 6px;
  padding: 12px;
}

.market-card strong {
  color: #111827;
  font-size: 1.25rem;
}

.market-card p,
.market-label {
  color: #667085;
  margin: 0;
}

.market-label {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.compact-history {
  border-top: 1px solid #edf0f4;
}

@media (max-width: 760px) {
  .market-grid {
    grid-template-columns: 1fr;
  }

  .market-heading {
    display: grid;
  }
}
```

- [ ] **Step 4: Run frontend checks**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npm run lint
npx playwright test --grep "watchlist renders market snapshot|watchlist can query|navigation links"
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/web/src/components/market-snapshot-panel.tsx apps/web/src/app/watchlist/page.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "feat(web): add watchlist market snapshot"
```

---

### Task 6: Final Verification

**Files:**
- Modify only files touched by earlier tasks if verification exposes a failure.

- [ ] **Step 1: Run backend full test suite**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 2: Run frontend type check**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npm run lint
```

Expected: PASS.

- [ ] **Step 3: Run frontend production build**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npm run build
```

Expected: PASS and route list still includes `/watchlist`, `/settings`, and `/strategy-lab`.

- [ ] **Step 4: Run Playwright E2E**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npx playwright test
```

Expected: all Playwright tests PASS.

- [ ] **Step 5: Validate Compose config**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if (Test-Path $dockerBin) { $env:Path = "$dockerBin;$env:Path" }
docker compose config
```

Expected: command exits successfully and prints merged Compose config. If Docker CLI is unavailable, record the exact error; the app must still tolerate Docker/LEAN unavailable status.

- [ ] **Step 6: Browser verification**

With the dev server available at `http://127.0.0.1:3000`, verify:

- `/watchlist` shows `市场快照`.
- Default `NVDA` snapshot shows a price or unavailable/fallback message.
- Querying `TSLA` changes the selected ticker to `TSLA`.
- `/settings` still shows `数据源状态`.
- `/strategy-lab` still shows Docker and LEAN readiness.
- Dashboard and AI sidecar still render.

- [ ] **Step 7: Commit verification fixes if needed**

If code changed during verification:

```powershell
git add apps/api/app/data/providers/base.py apps/api/app/data/providers/mock.py apps/api/app/data/providers/openbb_optional.py apps/api/app/data/providers/registry.py apps/api/app/api/routes/mvp.py apps/api/tests/test_market_data_contracts.py apps/api/tests/test_mock_provider.py apps/api/tests/test_openbb_optional_provider.py apps/api/tests/test_provider_registry.py apps/api/tests/test_mvp_routes.py apps/web/src/lib/client-api.ts apps/web/src/components/market-snapshot-panel.tsx apps/web/src/app/watchlist/page.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "fix: stabilize market data layer"
```

If no code changed:

```powershell
git status --short
```

Expected: clean working tree.

---

## Self-Review

- Spec coverage: quote, history, fundamentals, arbitrary ticker, default five symbols, OpenBB/yfinance, optional dependency behavior, fallback labels, market endpoints, Watchlist UI, and tests are covered.
- Scope control: broker connections, order placement, paid keys, live streaming, database caching, and real LEAN execution are excluded.
- Type consistency: backend models use `Quote`, `PriceHistoryBar`, `FundamentalSnapshot`, and `MarketSnapshot`; frontend payload names mirror those fields.
- TDD coverage: each implementation task starts with failing tests and has targeted pass commands before commit.
