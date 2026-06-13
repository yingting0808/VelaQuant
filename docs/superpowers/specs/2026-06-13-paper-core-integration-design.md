# Paper Trading Core Integration Design

## Objective

Make paper trading use the Trading Core as the mandatory execution path. The system should no longer let simulated orders bypass the event, intent, risk, and execution state-machine chain.

This moves VelaQuant closer to the requested stable daily loop:

```text
candidate -> explanation -> simulated order -> PnL -> strategy review
```

while preserving the paper-only boundary.

## Scope

In scope:

- persist Trading Core identifiers, risk decision, and state history on each `PaperOrder`;
- convert manual paper orders into `TradeIntent` and `PortfolioState`;
- require `ExecutionEngine.submit_intent` before any cash or position mutation;
- record rejected core decisions as rejected paper orders instead of raising for normal risk denials;
- let the daily paper loop optionally auto-submit a small number of generated candidates through the same core path;
- expose core audit fields in paper order API payloads.

Out of scope:

- live broker routing;
- LEAN integration changes;
- real market scheduler;
- front-end redesign;
- replacing all paper tables with event sourcing.

## Data Model

Extend `PaperOrder` with audit fields:

- `core_order_id`
- `core_intent_id`
- `risk_status`
- `risk_code`
- `risk_reason`
- `state_history_json`

These fields are nullable so existing local databases can continue to load rows created before this integration.

## Execution Flow

Manual order:

1. normalize request;
2. read quote;
3. build `PortfolioState` from current paper account and paper positions;
4. build a `TradeIntent`;
5. run `ExecutionEngine`;
6. persist a `PaperOrder` with the core audit fields;
7. mutate cash and positions only if the core order is `filled`.

Daily loop:

1. generate candidates as before;
2. mark positions to market;
3. auto-submit top candidates up to a conservative cap;
4. create a review snapshot after simulated execution.

The daily loop must use the same `submit_paper_order` code path so manual and automated simulation cannot diverge.

## Risk Defaults

Use conservative defaults for paper trading:

- max order notional: `DEFAULT_CANDIDATE_NOTIONAL`;
- max position weight: `0.10`;
- max daily orders: `5`.

These defaults keep the paper loop small and auditable.

## API Behavior

`GET /api/mvp/paper-trading/summary` and order responses should include:

- `core_order_id`
- `core_intent_id`
- `risk_status`
- `risk_code`
- `risk_reason`
- `state_history`

Risk-denied manual orders return a normal rejected order payload. Operational problems such as unusable quotes can still return errors.

## Tests

Backend tests must prove:

- buy paper order persists a filled Trading Core state history;
- oversized buy produces a rejected paper order with no cash or position mutation;
- daily loop can auto-submit candidates through Trading Core and include audit state;
- existing summary still returns candidates, orders, positions, and latest review.

