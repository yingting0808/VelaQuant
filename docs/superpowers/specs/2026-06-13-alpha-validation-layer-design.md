# Alpha Validation Layer Design

## Objective

Add the first strategy evaluation layer so the system can judge whether a paper strategy has enough evidence to consider promotion. This phase does not optimize a strategy and does not enable live trading. It turns existing paper-run data into a conservative alpha-readiness report.

## Scope

In scope:

- evaluate the current deterministic paper strategy from existing paper candidates, orders, reviews, and core event logs;
- calculate sample size, signal precision, filled/rejected order counts, expectancy, max drawdown, and a stability score;
- classify the strategy as `insufficient_sample`, `negative_expectancy`, `watch`, or `paper_ready`;
- expose the result through an API endpoint and a compact Strategy Lab panel.

Out of scope:

- live trading promotion;
- strategy mutation;
- A/B testing;
- market-regime attribution;
- multi-strategy ranking.

## Architecture

Create `app.services.strategy_evaluation` as a read-only service over the existing database models. The service is intentionally separate from `app.trading_core`: the core decides and executes; evaluation audits results after the fact.

```text
PaperCandidate / PaperOrder / PaperReview / CoreEventLog
  -> StrategyEvaluationService
  -> StrategyEvaluationPayload
  -> API / Strategy Lab UI
```

## Metrics

- `sample_size`: number of paper candidates observed.
- `filled_order_count`: filled simulated orders.
- `rejected_order_count`: rejected simulated orders.
- `closed_trade_count`: sell orders with realized PnL.
- `signal_precision`: share of filled orders that currently have non-negative realized or unrealized PnL.
- `expectancy`: latest paper review expectancy.
- `max_drawdown`: worst peak-to-trough decline from review equity history.
- `stability_score`: conservative score capped by sample size, expectancy, drawdown, and precision.

## Decision Rules

- Fewer than 20 filled orders: `insufficient_sample`.
- Non-positive expectancy after enough samples: `negative_expectancy`.
- Positive expectancy with 20-29 filled orders: `watch`.
- Positive expectancy with at least 30 filled orders and acceptable drawdown: `paper_ready`.

The first version should be conservative. A strategy can stay blocked for lack of evidence even if current unrealized PnL is positive.

## Testing

Tests must cover:

- no data returns an insufficient-sample report;
- seeded paper data returns filled/rejected counts and precision;
- review equity history produces drawdown;
- enough positive closed samples can reach `paper_ready`;
- API returns the evaluation payload.
