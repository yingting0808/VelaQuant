# Trading Core Events Design

## Goal

Upgrade the trading system toward an event-driven core without replacing the working paper-trading flow. This phase adds the missing event backbone and execution adapter boundary so candidates, strategy intents, risk decisions, order states, and later broker fills can be replayed and audited.

## Current Context

The backend already has `app.trading_core` with:

- `MarketEvent`: structured market or AI-understood facts, with no trade action fields.
- `TradeIntent`: deterministic strategy output.
- `RiskEngine`: central approval and rejection checks.
- `ExecutionEngine`: order state machine from `new` to `filled` or `rejected`.
- Paper trading integration: paper orders now persist core order ids, risk results, and state history.

The missing layer is an explicit event bus and broker adapter boundary. Today the engine returns orders directly, but it does not publish a replayable stream of what happened, and the execution engine is still coupled to a synchronous mock fill.

## Architecture Decision

Use a small synchronous in-memory event bus first. It is intentionally not Kafka, Redis Streams, or a queue service yet. The goal is to define the internal event protocol and make tests prove event order and risk gating. A durable backend can be added after the system has a stable event contract.

Add these units:

- `event_bus.py`: publishes typed `EventEnvelope` records in order and dispatches handlers by topic.
- `StrategyInputEvent`: immutable strategy input wrapper containing the structured market event and portfolio snapshot.
- `ExecutionAdapter` protocol: broker adapter boundary used by the execution engine after risk approval.
- `MockExecutionAdapter`: synchronous fill adapter used by paper trading and tests.
- `OrderStateEvent`: compact event emitted for order state transitions.

## Boundaries

AI remains outside trading decisions. AI can produce `MarketEvent` and research text, but cannot produce `TradeIntent`, order side, quantity, or broker instructions.

Strategies remain deterministic. A strategy consumes `MarketEvent` plus `PortfolioState` through `StrategyInputEvent` and emits `TradeIntent`. It does not call AI, data providers, brokers, or databases.

Risk is mandatory. `ExecutionEngine` evaluates risk before calling the execution adapter. Tests must prove rejected intents never reach the adapter.

Execution is state-machine based. Adapter fills are represented as reports and reflected in `CoreOrder.state_history`; callers must not mutate portfolio state unless the core order reaches `filled`.

## Event Flow

```text
MarketEvent
  -> EventBus(topic=market_event)
  -> StrategyInputEvent
  -> Strategy.generate_intents()
  -> EventBus(topic=trade_intent)
  -> ExecutionEngine
  -> RiskEngine
  -> ExecutionAdapter
  -> EventBus(topic=order_state)
```

## Out Of Scope For This Phase

- Durable event storage.
- Real broker adapters for IBKR or Alpaca.
- Asynchronous execution and partial fills from live broker callbacks.
- Rewriting paper trading candidate generation.
- Changing UI layout.

## Acceptance Criteria

- Trading core tests prove event bus publish order and handler dispatch.
- Trading engine emits market, strategy input, trade intent, and order state events.
- Rejected intents do not call the execution adapter.
- Filled orders are driven by adapter fill reports rather than hardcoded execution transitions.
- Existing paper trading service tests keep passing through the new execution boundary.
