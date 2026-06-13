# Paper Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route daily paper candidate generation through the Trading Core event, strategy, risk, and execution chain.

**Architecture:** Keep `app.trading_core` pure and make `app.services.paper_trading` act as an adapter that converts provider evidence into `MarketEvent`, calls `TradingEngine`, persists event envelopes, and maps generated `TradeIntent` objects into `PaperCandidate` rows.

**Tech Stack:** Python, SQLModel, Pydantic, pytest, existing paper trading service and Trading Core modules.

---

## File Structure

- Modify `apps/api/tests/test_paper_trading_service.py`: add failing coverage for full paper-run event chains and strategy-derived candidates.
- Modify `apps/api/app/services/paper_trading.py`: replace service-local candidate decisioning with `TradingEngine` event processing.
- No schema changes are required.

### Task 1: Red Test

- [ ] Add a test asserting a completed daily run persists `market_event`, `strategy_input`, `trade_intent`, and `order_state` events.
- [ ] Add assertions that the generated candidate thesis uses the core trade-intent reason.
- [ ] Run the targeted test and confirm it fails because only `order_state` events are currently persisted.

### Task 2: Core Pipeline Adapter

- [ ] Add helper functions in `paper_trading.py` to build `MarketEvent` objects from provider evidence.
- [ ] Add a helper that creates a `TradingEngine` with `DeterministicWatchlistStrategy`, `RiskEngine`, and `InMemoryEventBus`.
- [ ] Persist non-order core event envelopes from the engine before auto-submitting the selected candidate order.

### Task 3: Candidate Mapping

- [ ] Map each generated `TradeIntent` into a proposed `PaperCandidate`.
- [ ] Keep quantity sizing based on current quote and the core intent notional.
- [ ] Keep candidates ranked by deterministic score and ticker order.

### Task 4: Verification

- [ ] Run the targeted paper trading tests.
- [ ] Run the full API test suite.
- [ ] Commit the docs and implementation.
