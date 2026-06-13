# Paper Core Pipeline Design

## Objective

Move the daily paper-trading workflow from service-local candidate scoring to the Trading Core event pipeline. The daily loop must produce candidates and simulated orders from this chain:

```text
MarketEvent -> StrategyInputEvent -> TradeIntent -> RiskEngine -> ExecutionEngine
```

This phase makes the current paper run closer to a long-lived trading-system base without changing broker adapters, LEAN integration, or UI workflows.

## Boundaries

In scope:

- convert provider evidence for each watchlist or portfolio ticker into a structured `MarketEvent`;
- use `DeterministicWatchlistStrategy` to create `TradeIntent` objects;
- create `PaperCandidate` rows only from generated trade intents;
- persist the full core event chain for each daily paper run;
- keep manual paper orders routed through the existing risk and execution path.

Out of scope:

- live trading;
- new strategy types;
- asynchronous queues;
- changes to LEAN backtests;
- AI-generated buy or sell commands.

## Architecture

The paper service remains an adapter. It collects data and persists database records, but strategy decisions come from `app.trading_core`.

Data conversion is one-way:

```text
MarketDataProvider evidence
  -> MarketEvent
  -> TradingEngine.process_event()
  -> EventEnvelope history
  -> PaperCandidate rows
  -> existing paper execution path
```

The core package must stay free of SQLModel, provider, FastAPI, and broker dependencies.

## Event Semantics

Each candidate ticker creates one structured event:

- `source`: `ai_structured`, because provider evidence has already been normalized into a research signal;
- `event_type`: `news`;
- `sentiment`: `positive` when evidence exists, otherwise `neutral`;
- `confidence`: derived from evidence count and diversification bonus;
- `impact_score`: derived from evidence count and capped conservatively;
- `metadata`: includes evidence count and quote price, but no trade action fields.

Events that do not satisfy the deterministic strategy thresholds create no trade intents and therefore no candidates.

## Persistence

`CoreEventLog` rows for a completed paper run should include:

- `market_event`;
- `strategy_input`;
- `trade_intent`;
- `order_state`.

Manual orders can still persist only order-state events because they start from an explicit user order, not from market-event strategy generation.

## Testing

Tests must show:

- daily paper runs persist the full core event chain;
- paper candidates are created from trade intents and keep the intent reason;
- persisted market events do not include trade action fields;
- the existing order, review, run-ledger, and idempotency behavior remains unchanged.
