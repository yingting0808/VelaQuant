# Strategy Attribution v3 Design

> **Scope:** Extend the existing Strategy Attribution Layer. Do not rewrite the trading core, risk gate, execution state machine, paper trading loop, or lifecycle system.

## Goal

Make the attribution layer answer two missing alpha-screening questions:

- What part of observed PnL came from high-volatility market conditions?
- How risk-adjusted was each market-regime bucket?

## Design

`RegimePerformanceItem` adds:

- `sample_count`: number of return observations used for that regime bucket.
- `sharpe_proxy`: average daily return divided by realized daily volatility, with a 1% volatility floor to avoid overstating near-flat price histories.

This is intentionally named `sharpe_proxy`, not `sharpe_ratio`, because it is derived from short price-history slices grouped by ticker regime. It is useful for screening and ranking diagnostics, but it is not a replacement for LEAN/backtest Sharpe.

`AttributionComponent` adds:

- `volatility_component`: observed PnL from the `high_volatility` regime bucket.

The existing components remain stable:

- `trend_component`
- `timing_component`
- `risk_component`
- `noise_component`

## Data Flow

```text
CoreEventLog + PaperOrder + PaperPosition + PaperReview
  -> ticker diagnostics
  -> provider price history
  -> regime classification
  -> regime performance buckets
  -> expectancy decomposition
```

## UI Contract

The Strategy Lab attribution panel displays:

- volatility component contribution
- primary regime return
- primary regime volatility
- primary regime `sharpe_proxy`

## Non-Goals

- No Strategy Lifecycle Manager in this step.
- No live trading enablement.
- No broker integration.
- No claim that `sharpe_proxy` is production-grade alpha proof.

