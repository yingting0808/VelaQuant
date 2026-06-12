# Real Data and LEAN Foundation Design

Date: 2026-06-12
Status: Approved for written-spec review

## 1. Goal

This phase upgrades VelaQuant from a mock-only MVP into a research foundation that can ingest real public-market evidence and show whether the local strategy lab is ready for QuantConnect LEAN backtesting.

The deliverable is not a trading system. It is a data and readiness layer:

- Real SEC EDGAR filing evidence for supported US tickers.
- A provider architecture that can use mock data now and OpenBB-style adapters later.
- A Strategy Lab workspace that reports Docker, Compose, and LEAN readiness.
- A clear UI distinction between mock data, public SEC data, optional OpenBB data, and unavailable data.

## 2. Scope

Included:

- Provider registry with `mock`, `sec_edgar`, `openbb_optional`, and `hybrid` modes.
- SEC EDGAR adapter for company submissions and recent filing evidence.
- Ticker-to-CIK mapping for the initial supported universe.
- Backend status endpoint for data providers and strategy tooling.
- Frontend data-source status surface in Settings.
- New Strategy Lab navigation entry and page.
- LEAN readiness checks for Docker CLI, Docker Compose, Docker engine, and Lean CLI presence.
- Tests for provider normalization, SEC response parsing, status reporting, and frontend navigation.

Excluded:

- Real brokerage connection.
- Real order placement.
- AI-triggered order execution.
- Paid market-data subscriptions.
- Full OpenBB installation as a hard dependency.
- Running a real LEAN backtest in this phase.
- Downloading paid QuantConnect datasets.

## 3. Product Behavior

### 3.1 Data Source Modes

The app supports four modes:

- `mock`: deterministic current behavior, always available.
- `sec_edgar`: public SEC filings and company submission metadata.
- `openbb_optional`: optional adapter that reports unavailable when OpenBB is not installed.
- `hybrid`: uses mock quotes, SEC filing evidence, and any available optional providers.

The default mode for local development is `hybrid`. If SEC or OpenBB is unavailable, the UI must show that state plainly and continue with mock data instead of pretending the data is live.

### 3.2 SEC Filing Evidence

For supported tickers, the backend maps ticker to CIK, calls SEC submissions data, and converts recent filings into normalized evidence items.

The initial supported universe is deliberately small:

- AAPL
- MSFT
- NVDA
- AMZN
- META

Each normalized SEC filing evidence item includes:

- `ticker`
- `title`
- `summary`
- `source`
- `source_url`
- `observed_at`
- `form`
- `filing_date`
- `accession_number`

If a ticker has no CIK mapping, the API returns a structured unavailable state rather than raising an unhandled error.

### 3.3 OpenBB Optional Adapter

OpenBB is treated as a mature future data layer, but this phase does not make it a required runtime dependency. The adapter exposes the same provider interface and reports:

- `available: false`
- `reason: "OpenBB package is not installed"`

when the package cannot be imported.

This keeps local development stable while preserving the boundary for future quote, historical price, fundamentals, news, and calendar data.

### 3.4 Strategy Lab

The Strategy Lab is a new workspace for future quantitative research and LEAN backtesting.

In this phase it shows readiness only:

- Docker CLI version.
- Docker Compose version.
- Docker engine status.
- Lean CLI status.
- Whether local LEAN backtesting is currently possible.
- Human-readable next action when not ready.

Example states:

- `Ready`: Docker engine and Lean CLI are available.
- `Partial`: Docker CLI exists but engine is not responding.
- `Not installed`: required tool is missing.

The page must avoid implying that a backtest has run. It is a readiness dashboard, not a strategy execution UI yet.

## 4. Backend Architecture

### 4.1 Provider Interfaces

Extend the existing provider boundary instead of adding provider-specific logic to routes.

Core concepts:

- `ProviderStatus`: name, available, mode, message, checked_at, version.
- `FilingEvidence`: normalized SEC filing evidence.
- `StrategyToolStatus`: tool name, available, version, message.
- `StrategyLabStatus`: Docker, Compose, Docker engine, Lean CLI, can_run_backtests.

The route layer should ask services for provider data and status; it should not import SEC/OpenBB/LEAN implementation details directly.

### 4.2 SEC Adapter

The SEC adapter handles:

- CIK normalization to SEC's ten-digit format.
- User-Agent header configuration.
- HTTP timeout and failure handling.
- Parsing `recent` submission arrays into filing evidence.
- Returning empty structured results when no matching filing exists.

SEC network tests must use mocked HTTP responses. Real network calls are not required for automated tests.

### 4.3 Provider Registry

The registry chooses provider behavior from settings:

- `AI_STOCKS_DATA_MODE`
- `AI_STOCKS_SEC_USER_AGENT`
- `AI_STOCKS_SEC_TIMEOUT_SECONDS`

The MVP dashboard and AI research route use the registry instead of directly constructing `MockMarketDataProvider`.

### 4.4 Strategy Readiness Service

The readiness service runs local commands with short timeouts:

- `docker --version`
- `docker compose version`
- `docker info`
- `lean --version`

It must never hang a request. If a command times out or fails, the service returns an unavailable status with the captured reason.

## 5. API Design

New endpoints:

- `GET /api/mvp/data-sources/status`
- `GET /api/mvp/strategy-lab/status`

Updated endpoints:

- `GET /api/mvp/dashboard`
- `POST /api/mvp/research`

Dashboard additions:

- `data_sources`
- `provider_mode`
- `strategy_lab`

Research additions:

- SEC filing evidence is included when available.
- AI output keeps the existing evidence-insufficient behavior when real evidence cannot be found.

## 6. Frontend Design

### 6.1 Navigation

Add a `策略实验室` item to the left navigation.

The first screen remains the actual dashboard. Strategy Lab is a normal workspace route at `/strategy-lab`.

### 6.2 Settings Page

Settings shows a data-source status section:

- Current mode.
- Mock provider status.
- SEC EDGAR status.
- OpenBB status.
- Last checked time.

The UI should preserve provider names and technical identifiers in English where appropriate: `SEC EDGAR`, `OpenBB`, `Mock`, `API`, `Docker`, `LEAN`.

### 6.3 Strategy Lab Page

Strategy Lab shows a compact operational dashboard:

- Readiness summary.
- Tool status rows.
- Backtest capability state.
- Next action.

It must not include a fake strategy list or fake performance chart. Those belong to the next phase after readiness is real.

## 7. Error Handling

SEC failures:

- Timeout: status row says SEC request timed out.
- HTTP failure: include status code in backend message, but not a stack trace.
- Unsupported ticker: explain that CIK mapping is missing.
- Parse mismatch: return no evidence and record a provider message.

OpenBB missing:

- Report optional dependency unavailable.
- Do not fail dashboard or research routes.

Docker / LEAN readiness failures:

- Missing executable: report not installed.
- Engine not responding: report partial Docker state.
- Timeout: report that readiness check timed out.

AI evidence safety:

- If real evidence is unavailable, keep the existing "证据不足" behavior.

## 8. Testing Strategy

Backend tests:

- SEC CIK formatting and ticker mapping.
- SEC submission parsing from a fixed JSON fixture.
- SEC adapter timeout/failure returns structured unavailable status.
- Provider registry returns mock-only and hybrid providers.
- Dashboard route includes `data_sources` and does not fail when optional providers are unavailable.
- Research route includes SEC evidence when fixture data is available.
- Strategy readiness service handles available, missing, and timeout command outcomes.

Frontend tests:

- Navigation includes `策略实验室`.
- Strategy Lab page renders Docker, Compose, LEAN, and readiness state.
- Settings page renders data-source status.
- Existing dashboard and AI sidecar tests still pass.

Verification:

- `python -m pytest -v`
- `npm run lint`
- `npm run build`
- `npx playwright test`
- `docker compose config` when Docker CLI and engine are available.

## 9. Acceptance Criteria

This phase is complete when:

- The app can still run with no external API keys.
- The dashboard no longer hardcodes direct mock provider construction in route handlers.
- SEC filing evidence is available for at least one supported ticker through a normalized provider interface.
- Settings clearly shows provider status.
- Strategy Lab clearly shows Docker and LEAN readiness.
- Docker/LEAN not being ready does not break the app.
- Tests cover the new provider and readiness behavior.
- Existing MVP routes and UI remain usable.

## 10. References

- OpenBB Platform / ODP: https://docs.openbb.co/
- OpenBB Equity Quote model: https://docs.openbb.co/odp/python/data_models/EquityQuote
- OpenBB Equity Historical model: https://docs.openbb.co/odp/python/data_models/EquityHistorical
- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC data.gov access page: https://data.sec.gov/
- QuantConnect LEAN local backtest: https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-backtest
- QuantConnect LEAN CLI installation: https://www.quantconnect.com/docs/v2/lean-cli/installation/installing-lean-cli
