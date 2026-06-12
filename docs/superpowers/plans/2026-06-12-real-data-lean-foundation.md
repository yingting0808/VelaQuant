# Real Data and LEAN Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real SEC EDGAR filing evidence, provider status reporting, and a Strategy Lab readiness workspace without making Docker, OpenBB, or LEAN hard requirements for running the app.

**Architecture:** Extend the existing FastAPI provider boundary with small focused adapters and a registry, then surface provider and strategy-tool status through MVP API routes. The Next.js frontend keeps the dashboard as the first screen, adds a Strategy Lab route, and uses client-side status panels with safe fallbacks so missing external tools never break the UI.

**Tech Stack:** FastAPI, Pydantic, SQLModel-adjacent services, httpx, SEC EDGAR REST APIs, optional OpenBB import detection, subprocess-based Docker/LEAN readiness checks, Next.js App Router, React, TypeScript, Playwright, pytest.

---

## Execution Notes

- Worktree: `D:\Documents\AI美股\.worktrees\codex-mvp-foundation`
- The worktree already contains uncommitted MVP application changes. Do not revert them.
- For each task commit, stage only files listed in that task.
- Keep provider names and tool identifiers in English in the UI: `SEC EDGAR`, `OpenBB`, `Mock`, `Docker`, `Compose`, `LEAN`.
- Do not add broker connections, paid market-data integrations, order placement, or real LEAN backtest execution in this phase.

## File Structure

- Modify `apps/api/pyproject.toml`: move `httpx` into runtime dependencies because SEC provider uses it outside tests.
- Modify `apps/api/app/core/config.py`: add data mode, SEC User-Agent, SEC timeout, and strategy command timeout settings.
- Modify `apps/api/app/data/providers/base.py`: add provider status and SEC filing metadata fields to normalized evidence.
- Create `apps/api/app/data/providers/sec_edgar.py`: supported ticker-to-CIK map, SEC submissions client, filing evidence parser.
- Create `apps/api/app/data/providers/openbb_optional.py`: OpenBB availability probe and future adapter boundary.
- Create `apps/api/app/data/providers/registry.py`: provider construction for `mock`, `sec_edgar`, `openbb_optional`, and `hybrid`.
- Create `apps/api/app/services/strategy_lab.py`: Docker, Compose, engine, and Lean CLI readiness checks.
- Modify `apps/api/app/api/routes/mvp.py`: use provider registry, expose data-source and strategy-lab status endpoints.
- Create `apps/api/tests/test_provider_contracts.py`: contracts and settings tests.
- Create `apps/api/tests/test_sec_edgar_provider.py`: SEC parser and failure behavior tests.
- Create `apps/api/tests/test_provider_registry.py`: registry and optional OpenBB tests.
- Create `apps/api/tests/test_strategy_lab_service.py`: command readiness tests.
- Modify `apps/api/tests/test_mvp_routes.py`: dashboard/status/strategy route expectations.
- Modify `apps/web/src/lib/client-api.ts`: add data-source and strategy-lab status client functions.
- Modify `apps/web/src/components/nav-panel.tsx`: add `策略实验室`.
- Modify `apps/web/src/components/module-view.tsx`: keep existing settings module rows and leave strategy lab to its own page.
- Create `apps/web/src/components/data-source-status-panel.tsx`: settings status panel.
- Create `apps/web/src/components/strategy-lab-status-panel.tsx`: readiness panel.
- Modify `apps/web/src/app/settings/page.tsx`: render data-source status.
- Create `apps/web/src/app/strategy-lab/page.tsx`: render Strategy Lab workspace.
- Modify `apps/web/tests/mvp.spec.ts`: E2E coverage for status panels and Strategy Lab navigation.

---

### Task 1: Backend Provider Contracts and Settings

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/data/providers/base.py`
- Test: `apps/api/tests/test_provider_contracts.py`

- [ ] **Step 1: Write failing provider contract tests**

Create `apps/api/tests/test_provider_contracts.py`:

```python
from app.core.config import Settings
from app.data.providers.base import EvidenceItem, ProviderStatus


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


def test_settings_expose_data_provider_defaults():
    settings = Settings()

    assert settings.data_mode == "hybrid"
    assert settings.sec_timeout_seconds == 3.0
    assert "VelaQuant" in settings.sec_user_agent
    assert settings.strategy_command_timeout_seconds == 2.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_provider_contracts.py -v
```

Expected: FAIL because `ProviderStatus` and the new settings fields do not exist.

- [ ] **Step 3: Add runtime dependency and settings**

Update `apps/api/pyproject.toml` so `httpx` is in main dependencies:

```toml
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic-settings>=2.4.0",
  "sqlmodel>=0.0.22",
  "psycopg[binary]>=3.2.0",
  "python-multipart>=0.0.9",
  "openpyxl>=3.1.5",
  "langgraph>=0.2.0",
  "httpx>=0.27.0",
]
```

Keep `pytest` and `pytest-cov` in `[project.optional-dependencies].dev`; remove `httpx` from the dev-only list if it is still there.

Update `apps/api/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-us-stocks-api"
    database_url: str = "sqlite:///./local.db"
    cors_origin: str = "http://localhost:3000"
    data_mode: str = "hybrid"
    sec_user_agent: str = "VelaQuant research app contact@example.com"
    sec_timeout_seconds: float = 3.0
    strategy_command_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_STOCKS_")


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Extend provider data contracts**

Update `apps/api/app/data/providers/base.py`:

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
```

Add this method to `apps/api/app/data/providers/mock.py`:

```python
from datetime import UTC, datetime

from app.data.providers.base import EvidenceItem, ProviderStatus, Quote


def _checked_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MockMarketDataProvider:
    # keep existing get_quote and get_research_evidence methods

    def get_statuses(self) -> list[ProviderStatus]:
        return [
            ProviderStatus(
                name="Mock",
                mode="mock",
                available=True,
                message="Deterministic local fallback data is available.",
                checked_at=_checked_at(),
                version="local",
            )
        ]
```

- [ ] **Step 5: Run contract tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_provider_contracts.py tests/test_mock_provider.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add apps/api/pyproject.toml apps/api/app/core/config.py apps/api/app/data/providers/base.py apps/api/app/data/providers/mock.py apps/api/tests/test_provider_contracts.py
git commit -m "feat(api): add provider status contracts"
```

---

### Task 2: SEC EDGAR Provider

**Files:**
- Create: `apps/api/app/data/providers/sec_edgar.py`
- Test: `apps/api/tests/test_sec_edgar_provider.py`

- [ ] **Step 1: Write failing SEC provider tests**

Create `apps/api/tests/test_sec_edgar_provider.py`:

```python
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
    assert evidence[0].source_url.endswith("/aapl-20250927.htm")


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_sec_edgar_provider.py -v
```

Expected: FAIL because `app.data.providers.sec_edgar` does not exist.

- [ ] **Step 3: Implement SEC provider**

Create `apps/api/app/data/providers/sec_edgar.py`:

```python
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
        self.client = client or httpx.Client(timeout=timeout_seconds)

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

        payload = response.json()
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
    recent = payload.get("filings", {}).get("recent", {})
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    forms = recent.get("form", [])
    primary_documents = recent.get("primaryDocument", [])
    observed_at = _utc_now()
    evidence: list[EvidenceItem] = []

    for index, accession_number in enumerate(accession_numbers[:5]):
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


def _value_at(values: list[Any], index: int) -> str:
    if index >= len(values):
        return ""
    value = values[index]
    return str(value).strip() if value is not None else ""
```

- [ ] **Step 4: Run SEC tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_sec_edgar_provider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/api/app/data/providers/sec_edgar.py apps/api/tests/test_sec_edgar_provider.py
git commit -m "feat(api): add SEC EDGAR provider"
```

---

### Task 3: Provider Registry and MVP API Integration

**Files:**
- Create: `apps/api/app/data/providers/openbb_optional.py`
- Create: `apps/api/app/data/providers/registry.py`
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_provider_registry.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write failing registry tests**

Create `apps/api/tests/test_provider_registry.py`:

```python
from app.core.config import Settings
from app.data.providers.base import EvidenceItem, ProviderStatus
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


def test_openbb_optional_status_reports_missing_package_when_not_installed():
    provider = build_market_data_provider(Settings(data_mode="openbb_optional"))

    status = provider.get_statuses()[0]

    assert status.name == "OpenBB"
    assert status.mode == "openbb_optional"
    assert status.available is False
```

- [ ] **Step 2: Extend route tests before implementation**

Modify `apps/api/tests/test_mvp_routes.py` to add:

```python
def test_mvp_dashboard_route_includes_provider_and_strategy_status():
    client = TestClient(create_app())

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])
    assert "strategy_lab" in payload


def test_mvp_data_sources_status_route_returns_statuses():
    client = TestClient(create_app())

    response = client.get("/api/mvp/data-sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_mode"] == "hybrid"
    assert any(source["name"] == "Mock" for source in payload["data_sources"])
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_provider_registry.py tests/test_mvp_routes.py -v
```

Expected: FAIL because registry and status endpoint do not exist.

- [ ] **Step 4: Add OpenBB optional provider**

Create `apps/api/app/data/providers/openbb_optional.py`:

```python
from datetime import UTC, datetime
from importlib.util import find_spec

from app.data.providers.base import EvidenceItem, ProviderStatus, Quote


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class OpenBBOptionalProvider:
    def __init__(self) -> None:
        self.available = find_spec("openbb") is not None

    def get_quote(self, ticker: str) -> Quote:
        normalized = ticker.strip().upper()
        raise ValueError(f"OpenBB quote adapter is not enabled for {normalized}")

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        return []

    def get_statuses(self) -> list[ProviderStatus]:
        if self.available:
            return [
                ProviderStatus(
                    name="OpenBB",
                    mode="openbb_optional",
                    available=True,
                    message="OpenBB package is installed; quote and historical adapters are reserved for the next provider task.",
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
```

- [ ] **Step 5: Add provider registry**

Create `apps/api/app/data/providers/registry.py`:

```python
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
```

- [ ] **Step 6: Update MVP routes to use the registry**

Modify `apps/api/app/api/routes/mvp.py` so provider creation goes through a helper:

```python
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow
from app.core.config import get_settings
from app.data.providers.registry import build_market_data_provider
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.portfolio import PositionInput, calculate_exposure
from app.services.strategy_lab import get_strategy_lab_status
```

Add:

```python
def get_market_data_provider():
    return build_market_data_provider(get_settings())
```

Update `dashboard()`:

```python
@router.get("/dashboard")
def dashboard() -> dict:
    settings = get_settings()
    provider = get_market_data_provider()
    positions = [
        PositionInput(ticker="AAPL", quantity=10, price=provider.get_quote("AAPL").price),
        PositionInput(ticker="MSFT", quantity=5, price=provider.get_quote("MSFT").price),
    ]
    exposure = calculate_exposure(positions)
    alerts = generate_event_alerts(
        portfolio_tickers=[item.ticker for item in exposure.items],
        candidates=[
            AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="mock_sec"),
            AlertCandidate(ticker="NVDA", title="NVDA news", reason="News event", source="mock_news"),
        ],
    )
    return {
        "portfolio": {
            "name": "主组合",
            "total_market_value": exposure.total_market_value,
            "positions": [item.model_dump() for item in exposure.items],
        },
        "alerts": [alert.model_dump() for alert in alerts],
        "ai_prompts": [
            "解释当前页面",
            "识别组合风险",
            "生成多/中/空情景",
            "起草交易计划",
        ],
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
        "strategy_lab": get_strategy_lab_status().model_dump(),
    }
```

Add route:

```python
@router.get("/data-sources/status")
def data_sources_status() -> dict:
    settings = get_settings()
    provider = get_market_data_provider()
    return {
        "provider_mode": settings.data_mode,
        "data_sources": [status.model_dump() for status in provider.get_statuses()],
    }
```

Update `research()` to use the registry:

```python
@router.post("/research")
def research(body: ResearchBody) -> dict:
    provider = get_market_data_provider()
    evidence = [
        EvidenceItemInput(
            title=item.title,
            summary=item.summary,
            source=item.source,
            source_url=item.source_url,
        )
        for item in provider.get_research_evidence(body.ticker)
    ]
    result = run_research_workflow(
        ResearchRequest(ticker=body.ticker, question=body.question, evidence=evidence)
    )
    return result.model_dump()
```

The `get_strategy_lab_status` import will fail until Task 4 is implemented. For this task, add a temporary minimal service file in Step 7.

- [ ] **Step 7: Add temporary strategy status model used by dashboard**

Create `apps/api/app/services/strategy_lab.py`:

```python
from pydantic import BaseModel


class StrategyToolStatus(BaseModel):
    name: str
    available: bool
    version: str | None
    message: str


class StrategyLabStatus(BaseModel):
    can_run_backtests: bool
    summary: str
    tools: list[StrategyToolStatus]


def get_strategy_lab_status() -> StrategyLabStatus:
    return StrategyLabStatus(
        can_run_backtests=False,
        summary="Strategy Lab readiness checks are not configured yet.",
        tools=[],
    )
```

Task 4 replaces this minimal implementation with command checks.

- [ ] **Step 8: Run registry and route tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_provider_registry.py tests/test_mvp_routes.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add apps/api/app/data/providers/openbb_optional.py apps/api/app/data/providers/registry.py apps/api/app/api/routes/mvp.py apps/api/app/services/strategy_lab.py apps/api/tests/test_provider_registry.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): add provider registry and status routes"
```

---

### Task 4: Strategy Lab Readiness Service

**Files:**
- Modify: `apps/api/app/services/strategy_lab.py`
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_strategy_lab_service.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write failing readiness service tests**

Create `apps/api/tests/test_strategy_lab_service.py`:

```python
from subprocess import CompletedProcess, TimeoutExpired

from app.services.strategy_lab import get_strategy_lab_status


def successful_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    output = {
        ("docker", "--version"): "Docker version 29.5.3, build d1c06ef",
        ("docker", "compose", "version"): "Docker Compose version v5.1.4",
        ("docker", "info"): "Client:\n Version: 29.5.3\nServer:\n Containers: 0",
        ("lean", "--version"): "lean, version 1.0.200",
    }[tuple(command)]
    return CompletedProcess(command, 0, stdout=output, stderr="")


def missing_lean_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["lean", "--version"]:
        raise FileNotFoundError("lean")
    return successful_runner(command, timeout)


def timeout_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["docker", "info"]:
        raise TimeoutExpired(command, timeout)
    return successful_runner(command, timeout)


def test_strategy_lab_status_is_ready_when_all_tools_are_available():
    status = get_strategy_lab_status(command_runner=successful_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is True
    assert status.summary == "Docker and LEAN are ready for local backtest preparation."
    assert {tool.name for tool in status.tools} == {"Docker CLI", "Docker Compose", "Docker engine", "LEAN CLI"}


def test_strategy_lab_status_reports_missing_lean_cli():
    status = get_strategy_lab_status(command_runner=missing_lean_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is False
    lean = next(tool for tool in status.tools if tool.name == "LEAN CLI")
    assert lean.available is False
    assert "not installed" in lean.message


def test_strategy_lab_status_reports_docker_engine_timeout():
    status = get_strategy_lab_status(command_runner=timeout_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is False
    engine = next(tool for tool in status.tools if tool.name == "Docker engine")
    assert engine.available is False
    assert "timed out" in engine.message
```

- [ ] **Step 2: Extend route test for Strategy Lab endpoint**

Add to `apps/api/tests/test_mvp_routes.py`:

```python
def test_mvp_strategy_lab_status_route_returns_readiness_payload():
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/status")

    assert response.status_code == 200
    payload = response.json()
    assert "can_run_backtests" in payload
    assert "summary" in payload
    assert "tools" in payload
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_strategy_lab_service.py tests/test_mvp_routes.py -v
```

Expected: FAIL because the temporary strategy lab service has no command runner support and the route is missing.

- [ ] **Step 4: Implement readiness checks**

Replace `apps/api/app/services/strategy_lab.py` with:

```python
import subprocess
from collections.abc import Callable
from subprocess import CompletedProcess, TimeoutExpired

from app.core.config import get_settings
from pydantic import BaseModel


CommandRunner = Callable[[list[str], float], CompletedProcess[str]]


class StrategyToolStatus(BaseModel):
    name: str
    available: bool
    version: str | None
    message: str


class StrategyLabStatus(BaseModel):
    can_run_backtests: bool
    summary: str
    tools: list[StrategyToolStatus]


def default_command_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        shell=False,
        text=True,
        timeout=timeout,
    )


def get_strategy_lab_status(
    *,
    command_runner: CommandRunner = default_command_runner,
    timeout_seconds: float | None = None,
) -> StrategyLabStatus:
    settings = get_settings()
    timeout = timeout_seconds if timeout_seconds is not None else settings.strategy_command_timeout_seconds
    tools = [
        _check_tool("Docker CLI", ["docker", "--version"], command_runner, timeout),
        _check_tool("Docker Compose", ["docker", "compose", "version"], command_runner, timeout),
        _check_tool("Docker engine", ["docker", "info"], command_runner, timeout),
        _check_tool("LEAN CLI", ["lean", "--version"], command_runner, timeout),
    ]
    ready = all(tool.available for tool in tools)
    summary = (
        "Docker and LEAN are ready for local backtest preparation."
        if ready
        else "Strategy Lab is partially configured; review unavailable tools before running LEAN backtests."
    )
    return StrategyLabStatus(can_run_backtests=ready, summary=summary, tools=tools)


def _check_tool(
    name: str,
    command: list[str],
    command_runner: CommandRunner,
    timeout: float,
) -> StrategyToolStatus:
    try:
        completed = command_runner(command, timeout)
    except FileNotFoundError:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=f"{name} is not installed or is not on PATH.",
        )
    except TimeoutExpired:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=f"{name} check timed out after {timeout:.1f}s.",
        )

    output = (completed.stdout or completed.stderr or "").strip()
    first_line = output.splitlines()[0] if output else ""
    if completed.returncode != 0:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=first_line or f"{name} returned exit code {completed.returncode}.",
        )

    return StrategyToolStatus(
        name=name,
        available=True,
        version=first_line or "available",
        message=f"{name} is available.",
    )
```

- [ ] **Step 5: Add Strategy Lab API route**

Add to `apps/api/app/api/routes/mvp.py`:

```python
@router.get("/strategy-lab/status")
def strategy_lab_status() -> dict:
    return get_strategy_lab_status().model_dump()
```

- [ ] **Step 6: Run strategy tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\api
python -m pytest tests/test_strategy_lab_service.py tests/test_mvp_routes.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add apps/api/app/services/strategy_lab.py apps/api/app/api/routes/mvp.py apps/api/tests/test_strategy_lab_service.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): report strategy lab readiness"
```

---

### Task 5: Frontend Status Clients and E2E Tests

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Add failing E2E tests for settings and Strategy Lab**

Add to `apps/web/tests/mvp.spec.ts`:

```ts
test("settings renders data source status", async ({ page }) => {
  await page.route("**/api/mvp/data-sources/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        provider_mode: "hybrid",
        data_sources: [
          {
            name: "Mock",
            mode: "mock",
            available: true,
            message: "Deterministic local fallback data is available.",
            checked_at: "2026-06-12T00:00:00Z",
            version: "local"
          },
          {
            name: "SEC EDGAR",
            mode: "sec_edgar",
            available: true,
            message: "SEC submissions adapter is configured.",
            checked_at: "2026-06-12T00:00:00Z",
            version: "data.sec.gov"
          }
        ]
      }
    });
  });

  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "数据源状态" })).toBeVisible();
  await expect(page.getByText("hybrid")).toBeVisible();
  await expect(page.getByText("SEC EDGAR")).toBeVisible();
});

test("strategy lab renders readiness status", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: false,
        summary: "Strategy Lab is partially configured; review unavailable tools before running LEAN backtests.",
        tools: [
          {
            name: "Docker CLI",
            available: true,
            version: "Docker version 29.5.3",
            message: "Docker CLI is available."
          },
          {
            name: "LEAN CLI",
            available: false,
            version: null,
            message: "LEAN CLI is not installed or is not on PATH."
          }
        ]
      }
    });
  });

  await gotoDashboard(page);
  await page.getByRole("link", { name: "策略实验室" }).click();

  await expect(page).toHaveURL("/strategy-lab");
  await expect(page.getByRole("heading", { name: "策略实验室" })).toBeVisible();
  await expect(page.getByText("Docker CLI")).toBeVisible();
  await expect(page.getByText("LEAN CLI")).toBeVisible();
  await expect(page.getByText("不可回测")).toBeVisible();
});
```

- [ ] **Step 2: Run E2E tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npx playwright test --grep "settings renders data source status|strategy lab renders readiness status"
```

Expected: FAIL because the status UI and Strategy Lab navigation do not exist.

- [ ] **Step 3: Add frontend status client types and fallbacks**

Append to `apps/web/src/lib/client-api.ts`:

```ts
export type ProviderStatusPayload = {
  name: string;
  mode: string;
  available: boolean;
  message: string;
  checked_at: string;
  version: string | null;
};

export type DataSourcesStatusPayload = {
  provider_mode: string;
  data_sources: ProviderStatusPayload[];
};

export type StrategyToolStatusPayload = {
  name: string;
  available: boolean;
  version: string | null;
  message: string;
};

export type StrategyLabStatusPayload = {
  can_run_backtests: boolean;
  summary: string;
  tools: StrategyToolStatusPayload[];
};

const fallbackDataSourcesStatus: DataSourcesStatusPayload = {
  provider_mode: "hybrid",
  data_sources: [
    {
      name: "Mock",
      mode: "mock",
      available: true,
      message: "本地 Mock 数据可用。",
      checked_at: "local",
      version: "local"
    },
    {
      name: "SEC EDGAR",
      mode: "sec_edgar",
      available: false,
      message: "后端 API 暂不可用，无法确认 SEC EDGAR 状态。",
      checked_at: "local",
      version: null
    },
    {
      name: "OpenBB",
      mode: "openbb_optional",
      available: false,
      message: "OpenBB 为可选数据层，当前未确认。",
      checked_at: "local",
      version: null
    }
  ]
};

const fallbackStrategyLabStatus: StrategyLabStatusPayload = {
  can_run_backtests: false,
  summary: "后端 API 暂不可用，无法确认 Docker / LEAN 状态。",
  tools: [
    {
      name: "Docker CLI",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "Docker Compose",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "Docker engine",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "LEAN CLI",
      available: false,
      version: null,
      message: "状态未确认。"
    }
  ]
};

function isProviderStatus(value: unknown): value is ProviderStatusPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.mode === "string" &&
    typeof value.available === "boolean" &&
    typeof value.message === "string" &&
    typeof value.checked_at === "string" &&
    (typeof value.version === "string" || value.version === null)
  );
}

function isDataSourcesStatusPayload(value: unknown): value is DataSourcesStatusPayload {
  return (
    isRecord(value) &&
    typeof value.provider_mode === "string" &&
    Array.isArray(value.data_sources) &&
    value.data_sources.every(isProviderStatus)
  );
}

function isStrategyToolStatus(value: unknown): value is StrategyToolStatusPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.available === "boolean" &&
    (typeof value.version === "string" || value.version === null) &&
    typeof value.message === "string"
  );
}

function isStrategyLabStatusPayload(value: unknown): value is StrategyLabStatusPayload {
  return (
    isRecord(value) &&
    typeof value.can_run_backtests === "boolean" &&
    typeof value.summary === "string" &&
    Array.isArray(value.tools) &&
    value.tools.every(isStrategyToolStatus)
  );
}

export async function getDataSourcesStatus(): Promise<DataSourcesStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/data-sources/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackDataSourcesStatus;
    }
    const payload: unknown = await response.json();
    return isDataSourcesStatusPayload(payload) ? payload : fallbackDataSourcesStatus;
  } catch {
    return fallbackDataSourcesStatus;
  }
}

export async function getStrategyLabStatus(): Promise<StrategyLabStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyLabStatus;
    }
    const payload: unknown = await response.json();
    return isStrategyLabStatusPayload(payload) ? payload : fallbackStrategyLabStatus;
  } catch {
    return fallbackStrategyLabStatus;
  }
}
```

- [ ] **Step 4: Run TypeScript check**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add apps/web/src/lib/client-api.ts apps/web/tests/mvp.spec.ts
git commit -m "test(web): cover data and strategy status"
```

---

### Task 6: Frontend Status Panels and Strategy Lab Workspace

**Files:**
- Modify: `apps/web/src/components/nav-panel.tsx`
- Create: `apps/web/src/components/data-source-status-panel.tsx`
- Create: `apps/web/src/components/strategy-lab-status-panel.tsx`
- Modify: `apps/web/src/app/settings/page.tsx`
- Create: `apps/web/src/app/strategy-lab/page.tsx`
- Modify: `apps/web/src/app/styles.css`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Add Strategy Lab navigation**

Modify `apps/web/src/components/nav-panel.tsx` to import `FlaskConical` from `lucide-react` and add:

```ts
{ label: "策略实验室", href: "/strategy-lab", icon: FlaskConical }
```

inside `navItems`, after `研究笔记` and before `数据导入`.

- [ ] **Step 2: Create data-source status panel**

Create `apps/web/src/components/data-source-status-panel.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { getDataSourcesStatus, type DataSourcesStatusPayload } from "@/lib/client-api";

export function DataSourceStatusPanel() {
  const [status, setStatus] = useState<DataSourcesStatusPayload | null>(null);

  useEffect(() => {
    let active = true;
    getDataSourcesStatus().then((payload) => {
      if (active) {
        setStatus(payload);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="data-panel status-panel" aria-label="数据源状态">
      <div className="panel-heading">
        <div>
          <h3>数据源状态</h3>
          <p>区分 Mock、本地 API、SEC EDGAR 和可选 OpenBB 数据层</p>
        </div>
        <span className="status-pill neutral">{status?.provider_mode ?? "加载中"}</span>
      </div>

      <div className="module-list">
        {(status?.data_sources ?? []).map((source) => (
          <article className="module-row" key={`${source.mode}-${source.name}`}>
            <div>
              <strong>{source.name}</strong>
              <p>{source.message}</p>
            </div>
            <span className={source.available ? "state-ok" : "state-warn"}>
              {source.available ? "可用" : "未就绪"}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Render data-source status on settings page**

Modify `apps/web/src/app/settings/page.tsx`:

```tsx
import { DataSourceStatusPanel } from "@/components/data-source-status-panel";
import { AppShell } from "@/components/app-shell";
import { ModuleView } from "@/components/module-view";
import { sampleDashboard } from "@/lib/sample-data";

export default function SettingsPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-stack">
        <ModuleView module="settings" />
        <DataSourceStatusPanel />
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 4: Create Strategy Lab panel**

Create `apps/web/src/components/strategy-lab-status-panel.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { getStrategyLabStatus, type StrategyLabStatusPayload } from "@/lib/client-api";

export function StrategyLabStatusPanel() {
  const [status, setStatus] = useState<StrategyLabStatusPayload | null>(null);

  useEffect(() => {
    let active = true;
    getStrategyLabStatus().then((payload) => {
      if (active) {
        setStatus(payload);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const canRun = status?.can_run_backtests ?? false;

  return (
    <section className="data-panel status-panel" aria-label="策略实验室状态">
      <div className="panel-heading">
        <div>
          <h3>回测环境</h3>
          <p>{status?.summary ?? "正在检查 Docker / Compose / LEAN 状态"}</p>
        </div>
        <span className={canRun ? "status-pill success" : "status-pill warning"}>
          {canRun ? "可回测" : "不可回测"}
        </span>
      </div>

      <div className="module-list">
        {(status?.tools ?? []).map((tool) => (
          <article className="module-row" key={tool.name}>
            <div>
              <strong>{tool.name}</strong>
              <p>{tool.message}</p>
            </div>
            <span className={tool.available ? "state-ok" : "state-warn"}>
              {tool.version ?? "未就绪"}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Add Strategy Lab page**

Create `apps/web/src/app/strategy-lab/page.tsx`:

```tsx
import { AppShell } from "@/components/app-shell";
import { StrategyLabStatusPanel } from "@/components/strategy-lab-status-panel";
import { sampleDashboard } from "@/lib/sample-data";

export default function StrategyLabPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-view">
        <header className="page-header">
          <div>
            <p>LEAN 回测预备环境与数据源就绪度</p>
            <h2>策略实验室</h2>
          </div>
          <div className="status-pill neutral">预备</div>
        </header>

        <StrategyLabStatusPanel />
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 6: Add small layout styles**

Append to `apps/web/src/app/styles.css`:

```css
.module-stack {
  display: grid;
  gap: 16px;
}

.status-panel {
  overflow: hidden;
}

.status-pill.success {
  background: #dcfce7;
  border-color: #86efac;
  color: #166534;
}

.status-pill.warning {
  background: #fff7ed;
  border-color: #fdba74;
  color: #9a3412;
}

.state-ok {
  color: #166534;
  font-weight: 700;
}

.state-warn {
  color: #9a3412;
  font-weight: 700;
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npm run lint
npx playwright test --grep "settings renders data source status|strategy lab renders readiness status|navigation links"
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add apps/web/src/components/nav-panel.tsx apps/web/src/components/data-source-status-panel.tsx apps/web/src/components/strategy-lab-status-panel.tsx apps/web/src/app/settings/page.tsx apps/web/src/app/strategy-lab/page.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "feat(web): add data source and strategy lab status"
```

---

### Task 7: Final Verification

**Files:**
- Modify only files touched by earlier tasks if verification exposes failures.

- [ ] **Step 1: Run backend tests**

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

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npm run build
```

Expected: build exits successfully and includes `/strategy-lab`.

- [ ] **Step 4: Run E2E tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation\apps\web
npx playwright test
```

Expected: all Playwright tests PASS.

- [ ] **Step 5: Validate Docker Compose when engine is ready**

Refresh the current shell PATH for Docker Desktop if needed:

```powershell
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
$env:Path = "$dockerBin;$env:Path"
```

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-mvp-foundation
docker compose config
```

Expected when Docker CLI is available: command exits successfully and prints merged Compose config.

If Docker engine is still not ready, do not fail the application work. Record the exact Docker error in the final report because the app is required to tolerate Docker/LEAN unavailable status.

- [ ] **Step 6: Verify browser manually**

With the dev server running at `http://127.0.0.1:3000`, verify:

- `策略实验室` appears in the left navigation.
- `/strategy-lab` shows `Docker CLI`, `Docker Compose`, `Docker engine`, and `LEAN CLI`.
- `/settings` shows `数据源状态`, `Mock`, `SEC EDGAR`, and `OpenBB`.
- Dashboard and AI sidecar still render.

- [ ] **Step 7: Commit verification fixes if any**

If verification required code changes, stage only those files and run:

```powershell
git commit -m "fix: stabilize real data and strategy readiness"
```

If no code changes were needed, run:

```powershell
git status --short
```

Expected: only pre-existing unrelated worktree changes remain.

---

## Self-Review

- Spec coverage: provider registry, SEC EDGAR evidence, OpenBB optional status, strategy readiness checks, settings UI, Strategy Lab UI, tests, and final verification are covered by Tasks 1-7.
- Scope control: the plan avoids broker writes, order placement, paid subscriptions, real LEAN backtest execution, and forced OpenBB installation.
- Type consistency: backend status names use `ProviderStatus`, `StrategyToolStatus`, and `StrategyLabStatus`; frontend payload types mirror those names and fields.
- External references used: SEC EDGAR APIs, SEC fair-access guidance, OpenBB Equity Historical/Quote docs, and QuantConnect LEAN CLI Docker/backtest docs.
