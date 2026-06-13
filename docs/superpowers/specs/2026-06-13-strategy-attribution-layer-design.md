# Strategy Attribution Layer Design

## Objective

Add the first Strategy Attribution Layer so the system can explain why the current paper strategy is behaving well or poorly. This layer complements Alpha Evaluation. Evaluation answers whether a strategy can advance; attribution starts answering why the result happened.

## Scope

In scope:

- read existing paper candidates, paper orders, paper positions, paper reviews, and core event logs;
- decompose current PnL into realized and unrealized components;
- diagnose signal quality from `market_event` and `trade_intent` event chains;
- classify current review equity behavior into a conservative market-regime proxy;
- return data-quality flags instead of pretending to know what the system has not measured;
- expose the attribution report through API and Strategy Lab UI.

Out of scope:

- live trading;
- full factor attribution;
- external market-regime models;
- strategy lifecycle promotion or kill switch;
- rewriting Trading Core or Alpha Evaluation.

## Architecture

Create `app.services.strategy_attribution` as a read-only service. It does not import `app.trading_core` and does not mutate trading state.

```text
CoreEventLog + PaperOrder + PaperPosition + PaperReview
  -> StrategyAttributionService
  -> StrategyAttributionPayload
  -> API / Strategy Lab UI
```

Alpha Evaluation remains the gate. Attribution supplies explanatory diagnostics that future lifecycle logic can use.

## Attribution V1 Metrics

### Signal Quality

- `market_event_count`: number of persisted market events.
- `trade_intent_count`: number of persisted trade intents.
- `actionable_signal_rate`: trade intents divided by market events.
- `average_confidence`: average confidence from persisted market event payloads.
- `false_positive_rate`: share of filled orders currently tied to negative realized or unrealized PnL.

### Expectancy Decomposition

- `realized_pnl`: realized PnL from paper orders.
- `unrealized_pnl`: unrealized PnL from paper positions.
- `open_trade_component`: unrealized PnL contribution.
- `closed_trade_component`: realized PnL contribution.

### Market Regime Proxy

Because the current system does not yet store broad market index series, v1 uses paper-review equity behavior:

- `insufficient_data`: fewer than three reviews;
- `drawdown_pressure`: max drawdown above 10%;
- `uptrend_capture`: latest equity is at least 2% above first review equity;
- `range_bound`: otherwise.

This is deliberately labeled as a proxy.

### Drawdown Attribution

V1 reports drawdown source as:

- `insufficient_data` if review history is too short;
- `open_position_pressure` if unrealized PnL is negative during drawdown;
- `closed_trade_losses` if realized PnL is negative during drawdown;
- `equity_curve_pressure` otherwise.

## API

Add `GET /api/mvp/strategy-lab/attribution`.

The payload must include:

- strategy id/name;
- signal quality summary;
- PnL decomposition;
- regime proxy;
- drawdown attribution;
- data quality warnings.

## UI

Add a compact `归因分析` panel under Strategy Lab, next to Alpha Evaluation. It should show:

- regime proxy;
- actionable signal rate;
- false positive rate;
- realized/unrealized PnL;
- drawdown source;
- data-quality warning count.

## Testing

Backend tests must prove:

- empty data returns insufficient-data attribution;
- event logs produce signal quality metrics;
- open losing positions increase false-positive rate;
- review equity history produces regime proxy and drawdown source.

Frontend tests must prove:

- Strategy Lab renders the attribution panel from API data.
