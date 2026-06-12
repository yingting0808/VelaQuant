# Trading Core v2 Foundation Design

## Objective

Upgrade VelaQuant from a platform-style MVP into a long-lived trading-system foundation by introducing an independent event-driven Trading Core. The first v2 slice must make the architectural boundaries explicit and testable:

1. AI structures information into events, but never emits trade commands.
2. Strategies are deterministic functions from structured events and portfolio state to trade intents.
3. Risk is a mandatory gatekeeper before execution.
4. Execution is state-machine based and auditable.

This phase builds the foundation beside the existing paper trading workflow. It does not replace the current paper trading UI or database service yet.

## Core Principle

The system must separate information, decision, risk, and execution:

```text
Market/AI/Event Input
  -> MarketEvent
  -> Strategy
  -> TradeIntent
  -> RiskEngine
  -> ExecutionEngine
  -> OrderState history
```

The Trading Core owns this chain. UI, API routes, LEAN, broker adapters, and AI workflows are external callers or adapters.

## Scope

This implementation adds a pure backend core module with no database dependency and a diagnostic dry-run API. The goal is architectural correctness, testability, and replayability.

In scope:

- structured event schema for market, news, earnings, filings, analyst, macro, and AI-structured events;
- deterministic strategy protocol and one small sample strategy;
- portfolio state objects used by strategy and risk;
- trade intent object that represents desired action but is not an order;
- mandatory risk evaluation for every intent;
- order state machine with state history;
- dry-run API that shows event to intent to risk to order transitions without mutating paper trading state.

Out of scope:

- replacing the existing paper trading tables;
- live broker APIs;
- real order routing;
- asynchronous queues;
- intraday scheduling;
- shorts, options, margin, tax lots, corporate actions;
- persistent event sourcing.

## Module Boundaries

Add `apps/api/app/trading_core/` with focused files:

- `events.py`: event enums and `MarketEvent`.
- `portfolio.py`: `PortfolioPosition` and `PortfolioState`.
- `strategy.py`: `TradeIntent`, `Strategy` protocol, and a deterministic watchlist strategy.
- `risk.py`: `RiskLimits`, `RiskDecision`, and `RiskEngine`.
- `execution.py`: `OrderState`, `CoreOrder`, and `ExecutionEngine`.
- `engine.py`: `TradingEngine` orchestration.

These files must not import SQLModel, FastAPI, OpenBB, LEAN, LangGraph, or broker SDKs. Adapters can call the core, but the core does not call adapters.

## Event Model

`MarketEvent` is the boundary for information entering strategy logic. It includes:

- `event_id`
- `source`
- `event_type`
- `ticker`
- `occurred_at`
- `summary`
- `sentiment`
- `confidence`
- `impact_score`
- `metadata`

It deliberately does not include `side`, `action`, `buy`, `sell`, `quantity`, or broker/order fields. AI workflows may produce this schema after reading news, filings, or research evidence, but they cannot decide trades.

## Strategy Model

Strategies are deterministic and side-effect free:

```text
input: MarketEvent + PortfolioState
output: list[TradeIntent]
```

Strategies must not perform network calls, AI calls, database writes, random sampling, or time-dependent logic. A strategy can decide that a structured event is actionable and output a `TradeIntent`, but that intent is not executable until risk approves it.

The first sample strategy is `DeterministicWatchlistStrategy`. It emits a small buy intent only when:

- ticker is in the configured watchlist;
- event confidence meets threshold;
- impact score meets threshold;
- sentiment is positive.

## Risk Model

`RiskEngine` is a gatekeeper, not a helper. Execution cannot transition to sent or filled unless the risk decision is approved.

The first limits are deliberately conservative:

- max notional per order;
- max portfolio weight per ticker after the order;
- max daily order count.

The engine exposes:

- `can_trade`
- `can_open_position`
- `can_increase_position`
- `can_trade_today`
- `evaluate`

Each rejection returns a code and human-readable reason for audit and UI display.

## Execution Model

Execution is a state machine. The first synchronous mock execution path supports:

```text
NEW -> VALIDATED -> RISK_APPROVED -> SENT -> FILLED
NEW -> VALIDATED -> REJECTED
```

Later broker adapters can extend this with partial fill, cancel, position closing, and close states. The foundation must record state history now so later execution can remain auditable.

## Dry-Run API

Add `POST /api/mvp/trading-core/dry-run`.

The route accepts a structured event, a simple portfolio state, and optional risk limits. It returns:

- normalized event;
- generated trade intents;
- risk decisions;
- order state histories.

It must not mutate database state and must not touch the current paper trading account.

## Error Handling

- Invalid event payloads return FastAPI validation errors.
- Events with unsupported or low-confidence information return no intents.
- Risk rejections return rejected order results, not HTTP failures.
- Core state-machine misuse raises clear Python exceptions in the core, but the dry-run route should use the normal `TradingEngine` path and avoid manual transitions.

## Testing

Backend tests must prove the architecture:

- `MarketEvent` cannot carry direct trade action fields.
- A strategy maps structured events to intents deterministically.
- Risk rejects oversized intents.
- Execution cannot fill a rejected intent.
- Approved execution state history includes `new`, `validated`, `risk_approved`, `sent`, and `filled`.
- The orchestrating engine runs event to strategy to risk to execution.
- The dry-run route returns the full chain without database mutation.

## Migration Path

This phase does not delete the existing paper trading service. Later phases should adapt paper candidate generation and simulated orders to call the Trading Core:

1. Convert research/news/provider evidence into `MarketEvent`.
2. Let strategies produce `TradeIntent`.
3. Require `RiskEngine.evaluate` before any simulated or live order.
4. Store `CoreOrder` state history alongside paper/live orders.
5. Route LEAN, IBKR, Alpaca, and mock adapters through a common execution adapter boundary.

