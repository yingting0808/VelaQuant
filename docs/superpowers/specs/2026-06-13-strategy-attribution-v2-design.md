# Strategy Attribution v2 Design

## Goal

Upgrade the current read-only Strategy Attribution Layer from portfolio-level summary metrics into an alpha-screening diagnostic surface. The system should answer which tickers and signal chains are contributing or hurting, whether open signals are decaying, and whether drawdowns look more like market pressure, signal failure, execution friction, or risk overreach.

## Non-goals

- Do not add Strategy Lifecycle Manager yet.
- Do not let AI generate trade decisions.
- Do not rewrite Trading Core, Execution Engine, Risk Engine, or the event ledger.
- Do not introduce a new market regime model that pretends to be statistically complete; v2 remains an explicit proxy until richer market data labels exist.

## Architecture

The implementation extends `app.services.strategy_attribution` as a read-only analytics layer. It reads `CoreEventLog`, `PaperOrder`, `PaperPosition`, and `PaperReview`, then derives a richer payload for the existing `GET /api/mvp/strategy-lab/attribution` endpoint.

The service will add:

- `ticker_diagnostics`: per-ticker event count, intent count, filled order count, false positive rate, average confidence, observed PnL, and open unrealized PnL.
- `signal_decay`: average holding days for open filled buy signals plus stale open positions based on an internal 5-day threshold.
- `expectancy_decomposition.components`: named proxy components for trend, timing, risk, and noise.
- `drawdown.contributors`: named contributors for market-driven pressure, signal failure, execution lag, and risk overreach.

## Data Rules

- Event payloads are parsed defensively. Malformed payloads add `malformed_event_payload` and are skipped.
- Ticker attribution uses event payload ticker first, then order and position tickers.
- False positives use the same v1 definition: losing sell orders or filled buy orders whose current open position is negative.
- Signal decay uses the latest timestamp among events, orders, positions, and reviews as `as_of`, so tests remain deterministic.
- Stale open signals are open positions whose most recent filled buy is at least 5 days old.
- Risk overreach is proxied by rejected orders and risk rejection metadata.
- Execution lag remains a placeholder proxy component with zero value until async broker timing exists, but the contributor is present so the contract is stable.

## UI

The Strategy Lab attribution panel should stay compact. It will display:

- top ticker drag / contribution row,
- average holding days and stale count,
- component chips for trend, timing, risk, and noise,
- contributor chips for market, signal, execution, and risk.

## Testing

Backend tests should prove:

- per-ticker diagnostics count events, intents, orders, confidence, and observed PnL,
- signal decay flags stale open positions deterministically,
- decomposition exposes trend/timing/risk/noise components,
- drawdown contributors include signal failure and risk overreach when data supports them.

Frontend tests should prove the Strategy Lab page renders these new fields from a mocked attribution response.
