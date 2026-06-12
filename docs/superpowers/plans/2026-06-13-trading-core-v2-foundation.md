# Trading Core v2 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a testable event-driven Trading Core foundation that separates AI event structuring, deterministic strategy decisions, mandatory risk gating, and execution state transitions.

**Architecture:** Implement a pure `app.trading_core` package with small Pydantic models and orchestration classes, then expose a non-mutating FastAPI dry-run route. Existing paper trading remains unchanged and can be migrated to the core in later phases.

**Tech Stack:** Python, Pydantic, FastAPI, pytest, existing `/api/mvp` route style.

---

## File Structure

- Create `apps/api/app/trading_core/__init__.py`: package exports for the core.
- Create `apps/api/app/trading_core/events.py`: event enums and `MarketEvent`.
- Create `apps/api/app/trading_core/portfolio.py`: portfolio state models.
- Create `apps/api/app/trading_core/strategy.py`: trade intent and deterministic strategy.
- Create `apps/api/app/trading_core/risk.py`: risk limits, decisions, and gatekeeper.
- Create `apps/api/app/trading_core/execution.py`: order model and state machine.
- Create `apps/api/app/trading_core/engine.py`: event-to-order orchestrator.
- Modify `apps/api/app/api/routes/mvp.py`: add dry-run request/response models and route.
- Create `apps/api/tests/test_trading_core.py`: core unit tests.
- Modify `apps/api/tests/test_mvp_routes.py`: dry-run API test.

### Task 1: Event And Strategy Contracts

**Files:**
- Create: `apps/api/tests/test_trading_core.py`
- Create: `apps/api/app/trading_core/__init__.py`
- Create: `apps/api/app/trading_core/events.py`
- Create: `apps/api/app/trading_core/portfolio.py`
- Create: `apps/api/app/trading_core/strategy.py`

- [ ] **Step 1: Write failing contract tests**

```python
from datetime import datetime, timezone

from app.trading_core.events import EventSource, MarketEvent, MarketEventType, Sentiment
from app.trading_core.portfolio import PortfolioState
from app.trading_core.strategy import DeterministicWatchlistStrategy, TradeIntentSide


def _event() -> MarketEvent:
    return MarketEvent(
        source=EventSource.ai_structured,
        event_type=MarketEventType.earnings,
        ticker="NVDA",
        occurred_at=datetime(2026, 6, 13, tzinfo=timezone.utc),
        summary="NVDA reported stronger than expected data center revenue.",
        sentiment=Sentiment.positive,
        confidence=0.86,
        impact_score=0.74,
    )


def test_market_event_schema_does_not_include_trade_action_fields():
    event = _event()

    payload = event.model_dump()

    assert "side" not in payload
    assert "action" not in payload
    assert "quantity" not in payload
    assert "order_type" not in payload


def test_strategy_converts_structured_event_to_trade_intent_deterministically():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    portfolio = PortfolioState(cash=100000, equity=100000)

    first = strategy.generate_intents(_event(), portfolio)
    second = strategy.generate_intents(_event(), portfolio)

    assert first == second
    assert len(first) == 1
    assert first[0].ticker == "NVDA"
    assert first[0].side == TradeIntentSide.buy
    assert first[0].notional == 1500
```

- [ ] **Step 2: Run tests to verify import failure**

Run: `python -m pytest tests/test_trading_core.py -q`

Expected: FAIL because `app.trading_core` does not exist.

- [ ] **Step 3: Implement minimal event, portfolio, and strategy models**

Create focused Pydantic models and a deterministic strategy that emits one buy intent for positive high-confidence watchlist events.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_trading_core.py -q`

Expected: PASS for the first two tests.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_trading_core.py apps/api/app/trading_core
git commit -m "feat(api): add trading core event strategy contracts"
```

### Task 2: Risk Gatekeeper

**Files:**
- Modify: `apps/api/tests/test_trading_core.py`
- Create: `apps/api/app/trading_core/risk.py`

- [ ] **Step 1: Write failing risk tests**

```python
from app.trading_core.risk import RiskDecisionStatus, RiskEngine, RiskLimits
from app.trading_core.strategy import TradeIntent, TradeIntentSide


def test_risk_engine_rejects_oversized_trade_intent():
    risk = RiskEngine(RiskLimits(max_order_notional=1000))
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=5000, reason="test")

    decision = risk.evaluate(intent, portfolio)

    assert decision.status == RiskDecisionStatus.rejected
    assert decision.code == "max_order_notional"
    assert "exceeds" in decision.reason
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_trading_core.py::test_risk_engine_rejects_oversized_trade_intent -q`

Expected: FAIL because `app.trading_core.risk` does not exist.

- [ ] **Step 3: Implement minimal risk engine**

Implement `RiskLimits`, `RiskDecisionStatus`, `RiskDecision`, and `RiskEngine.evaluate` with conservative checks.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_trading_core.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_trading_core.py apps/api/app/trading_core/risk.py
git commit -m "feat(api): add trading core risk gatekeeper"
```

### Task 3: Execution State Machine

**Files:**
- Modify: `apps/api/tests/test_trading_core.py`
- Create: `apps/api/app/trading_core/execution.py`

- [ ] **Step 1: Write failing execution tests**

```python
from app.trading_core.execution import ExecutionEngine, OrderState


def test_execution_engine_does_not_fill_rejected_intent():
    risk = RiskEngine(RiskLimits(max_order_notional=1000))
    execution = ExecutionEngine(risk)
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=5000, reason="test")

    order = execution.submit_intent(intent, portfolio)

    assert order.current_state == OrderState.rejected
    assert [state.state for state in order.state_history] == [OrderState.new, OrderState.validated, OrderState.rejected]
    assert order.risk_decision is not None
    assert order.risk_decision.status == RiskDecisionStatus.rejected


def test_execution_engine_records_approved_order_state_history():
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    execution = ExecutionEngine(risk)
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=1500, reason="test")

    order = execution.submit_intent(intent, portfolio)

    assert [state.state for state in order.state_history] == [
        OrderState.new,
        OrderState.validated,
        OrderState.risk_approved,
        OrderState.sent,
        OrderState.filled,
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_trading_core.py::test_execution_engine_does_not_fill_rejected_intent tests/test_trading_core.py::test_execution_engine_records_approved_order_state_history -q`

Expected: FAIL because `app.trading_core.execution` does not exist.

- [ ] **Step 3: Implement state machine**

Create `OrderState`, `OrderStateRecord`, `CoreOrder`, and `ExecutionEngine.submit_intent`. Execution must call risk before sent or filled.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_trading_core.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_trading_core.py apps/api/app/trading_core/execution.py
git commit -m "feat(api): add trading core execution state machine"
```

### Task 4: Trading Engine Orchestration

**Files:**
- Modify: `apps/api/tests/test_trading_core.py`
- Create: `apps/api/app/trading_core/engine.py`

- [ ] **Step 1: Write failing orchestration test**

```python
from app.trading_core.engine import TradingEngine


def test_trading_engine_processes_event_through_strategy_risk_and_execution():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    engine = TradingEngine(strategy=strategy, risk_engine=risk)
    portfolio = PortfolioState(cash=100000, equity=100000)

    result = engine.process_event(_event(), portfolio)

    assert len(result.intents) == 1
    assert len(result.orders) == 1
    assert result.orders[0].current_state == OrderState.filled
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_trading_core.py::test_trading_engine_processes_event_through_strategy_risk_and_execution -q`

Expected: FAIL because `app.trading_core.engine` does not exist.

- [ ] **Step 3: Implement orchestrator**

Wire strategy, risk, and execution into a simple result model.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_trading_core.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_trading_core.py apps/api/app/trading_core/engine.py apps/api/app/trading_core/__init__.py
git commit -m "feat(api): orchestrate trading core pipeline"
```

### Task 5: Dry-Run API

**Files:**
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/api/app/api/routes/mvp.py`

- [ ] **Step 1: Write failing route test**

```python
def test_trading_core_dry_run_returns_state_machine(client):
    response = client.post(
        "/api/mvp/trading-core/dry-run",
        json={
            "event": {
                "source": "ai_structured",
                "event_type": "earnings",
                "ticker": "NVDA",
                "occurred_at": "2026-06-13T00:00:00Z",
                "summary": "NVDA reported stronger than expected data center revenue.",
                "sentiment": "positive",
                "confidence": 0.86,
                "impact_score": 0.74,
            },
            "portfolio": {"cash": 100000, "equity": 100000, "positions": []},
            "watchlist": ["NVDA"],
            "risk_limits": {"max_order_notional": 5000},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["orders"][0]["current_state"] == "filled"
    assert [item["state"] for item in payload["orders"][0]["state_history"]] == [
        "new",
        "validated",
        "risk_approved",
        "sent",
        "filled",
    ]
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_mvp_routes.py::test_trading_core_dry_run_returns_state_machine -q`

Expected: FAIL with route not found.

- [ ] **Step 3: Add dry-run route**

Add Pydantic request model, instantiate the deterministic strategy, risk engine, and trading engine, then return `model_dump()` from the result.

- [ ] **Step 4: Run route test**

Run: `python -m pytest tests/test_mvp_routes.py::test_trading_core_dry_run_returns_state_machine -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/test_mvp_routes.py apps/api/app/api/routes/mvp.py
git commit -m "feat(api): expose trading core dry run"
```

### Task 6: Verification

**Files:**
- No production edits expected.

- [ ] **Step 1: Run focused core tests**

Run: `python -m pytest tests/test_trading_core.py tests/test_mvp_routes.py::test_trading_core_dry_run_returns_state_machine -q`

Expected: PASS.

- [ ] **Step 2: Run full API suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Run API health import check**

Run from repo root if Docker is active: `docker compose ps`

Expected: Services remain running; no restart is required for pure-code verification unless the local API needs the new route loaded.

- [ ] **Step 4: Call dry-run route on the running API if restarted**

Run: `Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/mvp/trading-core/dry-run -ContentType 'application/json' -Body '<json payload>'`

Expected: response includes one filled order state history.

