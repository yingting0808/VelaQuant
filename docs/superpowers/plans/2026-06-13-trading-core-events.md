# Trading Core Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a replayable event bus and execution adapter boundary to the existing Trading Core.

**Architecture:** Keep the current synchronous backend flow but formalize the core event stream. `TradingEngine` publishes event envelopes, `ExecutionEngine` routes approved orders through an adapter, and tests prove rejected orders cannot bypass risk.

**Tech Stack:** Python 3.12, Pydantic, pytest, FastAPI service code under `apps/api/app`.

---

### Task 1: Event Protocol

**Files:**
- Modify: `apps/api/app/trading_core/events.py`
- Create: `apps/api/app/trading_core/event_bus.py`
- Test: `apps/api/tests/test_trading_core.py`

- [ ] Write failing tests for event bus publish order and `StrategyInputEvent` validation.
- [ ] Run `python -m pytest apps/api/tests/test_trading_core.py -q` and confirm the new tests fail because the symbols do not exist.
- [ ] Add `StrategyInputEvent`, `TradingEventTopic`, `EventEnvelope`, and `InMemoryEventBus`.
- [ ] Re-run focused trading core tests and confirm they pass.
- [ ] Commit event protocol changes.

### Task 2: Execution Adapter Boundary

**Files:**
- Modify: `apps/api/app/trading_core/execution.py`
- Test: `apps/api/tests/test_trading_core.py`

- [ ] Write failing tests proving rejected orders do not call an adapter and approved orders use adapter fill reports.
- [ ] Run focused tests and confirm failures are about missing adapter behavior.
- [ ] Add `ExecutionAdapter`, `ExecutionReport`, and `MockExecutionAdapter`.
- [ ] Update `ExecutionEngine.submit_intent()` to call the adapter only after risk approval.
- [ ] Re-run focused trading core tests and confirm they pass.
- [ ] Commit adapter boundary changes.

### Task 3: Trading Engine Event Emission

**Files:**
- Modify: `apps/api/app/trading_core/engine.py`
- Test: `apps/api/tests/test_trading_core.py`

- [ ] Write a failing test for event topics emitted by `TradingEngine.process_event()`.
- [ ] Run focused tests and confirm the new test fails before implementation.
- [ ] Let `TradingEngine` accept an optional event bus and publish market, strategy input, trade intent, and order state events.
- [ ] Re-run focused trading core tests and confirm they pass.
- [ ] Run paper trading service tests to verify integration still works.
- [ ] Commit trading engine event emission.

### Task 4: Verification

**Files:**
- Existing backend test suite.

- [ ] Run `python -m pytest apps/api/tests/test_trading_core.py apps/api/tests/test_paper_trading_service.py -q`.
- [ ] Run full API tests with `python -m pytest apps/api/tests -q`.
- [ ] Merge the branch back to `master` only after tests pass.
