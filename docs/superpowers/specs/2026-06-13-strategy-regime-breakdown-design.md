# Strategy Regime Breakdown Design

## Goal

Upgrade Strategy Attribution so it can explain performance by market environment, not only by ticker, signal decay, and drawdown proxy. This closes the biggest remaining gap in the requested Strategy Attribution Layer: answering whether observed strategy behavior came from trend markets, range markets, high volatility, or insufficient data.

## Scope

- Extend the existing read-only `strategy_attribution` service.
- Keep Trading Core, Strategy, Risk, Execution, and Event Ledger unchanged.
- Keep AI out of trade decisions.
- Use the existing `MarketDataProvider.get_price_history()` contract.
- Preserve the current endpoint path: `GET /api/mvp/strategy-lab/attribution`.

## Regime Classification

For each ticker in attribution diagnostics:

- `insufficient_data`: fewer than three valid close prices.
- `high_volatility`: daily return volatility at or above 4%.
- `trend_market`: absolute price change from first close to latest close at or above 2%.
- `range_market`: all other valid histories.

The breakdown aggregates ticker count, observed PnL, average return, average volatility, and tickers by regime. It is still a proxy, but it is now driven by market history instead of only portfolio equity review records.

## API and UI

`StrategyAttributionPayload` gains `regime_breakdown: RegimeBreakdownPayload`. The UI displays the strongest regime row in the existing attribution panel, plus return and volatility. If no provider data exists, it returns an `insufficient_data` row with a warning rather than failing.

## Testing

Backend tests cover trend, range, high-volatility, and insufficient-data classification with a fake provider. Route tests ensure the provider is passed through. Frontend tests assert the Strategy Lab attribution panel renders the regime breakdown fields.
