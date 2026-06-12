# Real Market Data Layer Design

Date: 2026-06-12
Status: Ready for user review

## 1. Goal

This phase upgrades VelaQuant from provider readiness into a usable real-market-data layer. The app should retrieve quote, historical price, and fundamental snapshots through OpenBB when available, while still running safely without OpenBB, API keys, or network access.

The deliverable is a normalized data layer and first UI surfaces for real market data:

- Latest quote data for default and user-entered tickers.
- Historical OHLCV price bars for charting and future Strategy Lab work.
- Fundamental metrics for AI research context.
- Clear source labels so the user can distinguish OpenBB/yfinance data from local mock fallback.

This phase is still not a trading system.

## 2. Scope

Included:

- Default universe: AAPL, MSFT, NVDA, AMZN, META.
- API support for arbitrary user-entered US ticker symbols.
- OpenBB provider implementation using the free/no-key `yfinance` provider first.
- Normalized backend contracts for quote, price history, fundamentals, and market snapshot.
- Backend routes for quote, history, fundamentals, and aggregated snapshot.
- Frontend query flow on Watchlist or a reusable ticker data panel.
- Dashboard/watchlist display of quote source, price, change, volume, and fallback state.
- Tests with fake OpenBB clients; no live OpenBB network calls in automated tests.

Excluded:

- Broker connections.
- Order placement.
- AI-triggered execution.
- Paid data provider keys as a requirement.
- Real LEAN backtest execution.
- Intraday streaming, websockets, or live tick feeds.
- Production caching/database persistence for market data.

## 3. Product Behavior

### 3.1 Ticker Universe

The UI starts with the same five default symbols:

- AAPL
- MSFT
- NVDA
- AMZN
- META

The API and frontend ticker query box accept any non-empty ticker. The app normalizes user input by trimming whitespace and uppercasing symbols. Unknown or unsupported tickers return a structured unavailable state instead of crashing.

### 3.2 Data Priority

OpenBB is the preferred real-market-data adapter. The first provider target is `yfinance`, because it is broadly available through OpenBB and does not require local API keys for the MVP use case.

Data retrieval order:

1. Try OpenBB/yfinance for quote, history, and fundamentals.
2. If OpenBB is not installed, disabled, raises, or returns no usable data, return a structured unavailable result.
3. For dashboard display only, allow local mock fallback with an explicit source label.
4. For AI research evidence, do not use mock data as if it were real market evidence.

### 3.3 Quote Data

Quote data includes the fields needed for the dashboard and watchlist:

- `ticker`
- `price`
- `currency`
- `change`
- `change_percent`
- `volume`
- `source`
- `updated_at`
- `is_fallback`
- `message`

If OpenBB returns partial data, the adapter should keep usable fields and set missing fields to `None`. It should not manufacture market values.

### 3.4 Historical Price Data

Historical prices use normalized OHLCV bars:

- `ticker`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `source`

The initial supported intervals are:

- `1d`
- `1W`
- `1M`

The API accepts optional `start_date`, `end_date`, and `interval`, with a sensible default of daily bars over the recent period.

### 3.5 Fundamental Snapshot

Fundamental metrics use a compact normalized snapshot:

- `ticker`
- `market_cap`
- `pe_ratio`
- `eps`
- `price_to_sales`
- `price_to_book`
- `gross_margin`
- `profit_margin`
- `operating_margin`
- `debt_to_equity`
- `source`
- `period_ending`
- `updated_at`
- `is_fallback`
- `message`

The first implementation should use OpenBB `equity.fundamental.metrics` and map only fields that are available and useful. Unknown metrics remain `None`.

## 4. Backend Architecture

### 4.1 Provider Contracts

Extend `apps/api/app/data/providers/base.py` with:

- `PriceHistoryBar`
- `FundamentalSnapshot`
- `MarketSnapshot`
- Optional capability/status fields that describe quote, history, and fundamentals availability.

Extend `MarketDataProvider` with optional methods:

- `get_price_history(ticker, start_date=None, end_date=None, interval="1d")`
- `get_fundamentals(ticker)`
- `get_market_snapshot(ticker)`

Existing providers must remain usable. Mock providers can implement deterministic fallback values. SEC EDGAR does not need to provide quote/history/fundamentals.

### 4.2 OpenBB Adapter

Upgrade `OpenBBOptionalProvider` from package-status-only into a real optional adapter.

Design requirements:

- No import-time hard dependency on OpenBB.
- Constructor accepts an injectable OpenBB client/module for tests.
- If OpenBB cannot be imported, status reports unavailable and data methods return unavailable payloads.
- If OpenBB raises or returns malformed data, data methods return unavailable payloads and preserve the error in a safe user-readable message.
- Automated tests use fake OpenBB result objects with `to_df()` or `to_dataframe()` behavior.

Expected OpenBB calls:

- `obb.equity.price.quote(symbol=ticker, provider="yfinance")`
- `obb.equity.price.historical(symbol=ticker, provider="yfinance", interval=interval, start_date=start_date, end_date=end_date)`
- `obb.equity.fundamental.metrics(symbol=ticker, provider="yfinance")`

### 4.3 Registry Behavior

Registry mode behavior:

- `mock`: mock quote/history/fundamentals only.
- `sec_edgar`: SEC filing evidence plus mock quote fallback for dashboard continuity; no mock evidence masking for research.
- `openbb_optional`: OpenBB quote/history/fundamentals when available; mock fallback for display only.
- `hybrid`: OpenBB market data when available, SEC filing evidence when available, mock display fallback when needed.

The route layer continues to depend on provider interfaces, not OpenBB internals.

## 5. API Design

New endpoints:

- `GET /api/mvp/market/quote/{ticker}`
- `GET /api/mvp/market/history/{ticker}`
- `GET /api/mvp/market/fundamentals/{ticker}`
- `GET /api/mvp/market/snapshot/{ticker}`

Query parameters for history:

- `start_date`
- `end_date`
- `interval`

Snapshot response:

- `ticker`
- `quote`
- `fundamentals`
- `provider_mode`
- `data_sources`

All endpoints should return `200` with structured unavailable/fallback fields for expected data-source failures. Validation errors, such as an empty ticker or unsupported interval, should return `422`.

## 6. Frontend Design

### 6.1 Dashboard

The dashboard keeps the portfolio as the first screen. It adds compact market-data source labels where relevant:

- Quote source.
- Fallback state.
- Last updated time when available.

It must not imply live trading or real-time streaming.

### 6.2 Watchlist

Watchlist becomes the first real market-data workspace:

- Default rows for AAPL, MSFT, NVDA, AMZN, META.
- Ticker input for arbitrary symbol lookup.
- Snapshot panel for selected ticker.
- Rows show price, change, volume, source, and availability state.

The query should be ergonomic and simple: input ticker, submit, show data or unavailable state.

### 6.3 Fundamentals Panel

The selected ticker panel shows a compact fundamentals section:

- Market cap.
- PE.
- EPS.
- Margins where available.
- Source and fallback status.

Missing metrics are displayed as unavailable, not zero.

### 6.4 History Surface

This phase can expose historical data as a compact table or simple sparkline-style list. It should avoid adding a heavy charting library unless the repo already has one or the implementation plan identifies a clear need.

The purpose is to validate the data layer for future Strategy Lab work, not to build a full charting terminal yet.

## 7. Error Handling

OpenBB missing:

- Status says OpenBB is not installed.
- Market endpoints return unavailable real-data payloads.
- Dashboard/watchlist may show explicit mock fallback.

OpenBB provider failure:

- Capture a safe message.
- Do not expose stack traces.
- Preserve provider status so the UI can show which layer failed.

Malformed data:

- Treat as unavailable for the affected method only.
- Other data methods can still succeed.

Ticker not found:

- Return structured unavailable response for that ticker.
- UI shows the ticker and a concise unavailable reason.

AI evidence safety:

- Mock quote/history/fundamentals may support display.
- Mock data must not be converted into real research evidence.

## 8. Testing Strategy

Backend tests:

- OpenBB package missing status.
- OpenBB quote parsing from fake result object.
- OpenBB history parsing from fake tabular result.
- OpenBB fundamentals parsing from fake metrics result.
- OpenBB exception returns unavailable payload.
- Registry uses OpenBB market data when available.
- Registry falls back to mock display data without using mock as research evidence.
- Market endpoints validate empty ticker and interval.
- Snapshot endpoint aggregates quote, fundamentals, provider mode, and data sources.

Frontend tests:

- Watchlist renders default ticker rows.
- User can query an arbitrary ticker.
- Quote/source/fallback labels render from mocked API payloads.
- Fundamentals panel renders available metrics and unavailable metrics.
- API failure renders an unavailable state instead of a blank page.
- Existing dashboard, settings, AI sidecar, and Strategy Lab tests still pass.

Verification:

- `python -m pytest -v`
- `npm run lint`
- `npm run build`
- `npx playwright test`
- `docker compose config`

## 9. Acceptance Criteria

This phase is complete when:

- The app runs with no external API keys.
- OpenBB absence does not break backend or frontend.
- When OpenBB/yfinance is available, quote/history/fundamentals can be normalized for at least one supported ticker.
- Default watchlist still works offline via explicit fallback.
- Arbitrary ticker lookup returns useful data or a structured unavailable state.
- AI/research output does not treat mock market data as real evidence.
- Tests cover available, missing, failing, and malformed OpenBB behavior.

## 10. References

- OpenBB equity quote: https://docs.openbb.co/odp/python/reference/equity/price/quote
- OpenBB equity historical price: https://docs.openbb.co/odp/python/reference/equity/price/historical
- OpenBB equity fundamental metrics: https://docs.openbb.co/odp/python/reference/equity/fundamental/metrics
