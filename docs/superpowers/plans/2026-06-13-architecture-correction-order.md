# Architecture Correction Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current paper-trading runtime from direct execution paths to a strategy-control system where Strategy Registry, Lifecycle eligibility, Risk/Execution, and persistent Event Ledger are all on the execution path.

**Architecture:** The runtime will create strategy execution bindings from Strategy Registry, validate each binding through Lifecycle Manager, and route paper automation through TradingEngine with a persistent event bus. Manual paper orders will require a registered strategy id and will persist risk/order events, so no execution path can create orders without registry/lifecycle/ledger context.

**Tech Stack:** FastAPI, SQLModel/Postgres, Pydantic, pytest, existing trading_core services.

---

## Mandatory Technology Constraints

- API/service layer must remain FastAPI, Pydantic, and SQLModel.
- Scheduler work must remain APScheduler; async execution must use Python asyncio when needed.
- Storage must remain PostgreSQL for durable system state and Redis for event stream/cache expansion.
- Trading core must remain the in-repository implementation under `apps/api/app/trading_core/`.
- Strategy execution must enter through `StrategyRegistry -> StrategyEngine`.
- Event flow must stay `MarketEvent -> StrategyInput -> TradeIntent -> RiskDecision -> OrderState -> EventLedger`.
- LEAN is allowed only for research/lab backtests and must not enter production execution.
- vectorbt is allowed only for fast research and must not enter live trading.
- OpenBB is research/data-provider input only and must not bypass provider abstractions.
- AI integrations are research/explanation/suggestion only and must not generate `TradeIntent`, influence `ExecutionEngine`, or bypass `StrategyRegistry`.
- Do not introduce Backtrader, Zipline, freqtrade, or any broker logic that bypasses the trading core.

Hard rules:

1. `StrategyRegistry` is the only entry point for strategies.
2. `ExecutionEngine` must not be directly callable without event flow.
3. `EventLedger` must persist all production events without exceptions.

---

### Task 1: Registry Execution Binding

**Files:**
- Create: `apps/api/app/services/strategy_control.py`
- Modify: `apps/api/app/services/strategy_registry.py`
- Test: `apps/api/tests/test_strategy_control.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.services.strategy_control import StrategyExecutionBinding, StrategyExecutionMode, get_strategy_execution_binding
from app.services.workspace import get_or_create_default_workspace


def test_registered_paper_strategy_loads_execution_binding(session):
    workspace = get_or_create_default_workspace(session)

    binding = get_strategy_execution_binding(session, workspace.team.id, "deterministic_watchlist_v1")

    assert isinstance(binding, StrategyExecutionBinding)
    assert binding.strategy_id == "deterministic_watchlist_v1"
    assert binding.execution_mode == StrategyExecutionMode.paper
    assert binding.strategy is not None
    assert binding.supports_live is False


def test_unregistered_strategy_is_rejected(session):
    workspace = get_or_create_default_workspace(session)

    try:
        get_strategy_execution_binding(session, workspace.team.id, "missing_strategy")
    except ValueError as error:
        assert "Strategy is not registered for execution" in str(error)
    else:
        raise AssertionError("missing strategy should be rejected")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api; python -m pytest tests/test_strategy_control.py -v`

Expected: FAIL because `app.services.strategy_control` does not exist.

- [ ] **Step 3: Implement registry execution binding**

Create `StrategyExecutionBinding` and `get_strategy_execution_binding()` so the paper runtime loads `DeterministicWatchlistStrategy` only through this service. The service must reject catalog-only strategies and unknown ids.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api; python -m pytest tests/test_strategy_control.py -v`

Expected: PASS.

### Task 2: Lifecycle Execution Gate

**Files:**
- Modify: `apps/api/app/services/strategy_lifecycle.py`
- Modify: `apps/api/app/services/strategy_control.py`
- Test: `apps/api/tests/test_strategy_control.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.services.strategy_control import assert_strategy_execution_allowed


def test_paper_strategy_is_allowed_to_execute_in_paper_stage(session):
    assert_strategy_execution_allowed(session, "deterministic_watchlist_v1", requested_mode="paper")


def test_live_execution_is_rejected_when_lifecycle_is_paper(session):
    try:
        assert_strategy_execution_allowed(session, "deterministic_watchlist_v1", requested_mode="live")
    except ValueError as error:
        assert "Lifecycle does not allow execution mode live" in str(error)
    else:
        raise AssertionError("live execution should be blocked from paper stage")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api; python -m pytest tests/test_strategy_control.py -v`

Expected: FAIL because `assert_strategy_execution_allowed` does not exist.

- [ ] **Step 3: Implement lifecycle gate**

Add an execution eligibility function that reads `get_strategy_lifecycle()` and permits only `paper` execution when `current_stage == "paper"` and the strategy is not killed. Live modes must be rejected until lifecycle stage permits them.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api; python -m pytest tests/test_strategy_control.py -v`

Expected: PASS.

### Task 3: Persistent Event Ledger Enforcement

**Files:**
- Modify: `apps/api/app/services/paper_trading.py`
- Modify: `apps/api/app/services/event_ledger.py`
- Test: `apps/api/tests/test_paper_trading_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from sqlmodel import select

from app.domain.models import CoreEventLog
from app.services.paper_trading import run_daily_paper_trading_loop
from app.services.workspace import get_or_create_default_workspace


def test_daily_paper_run_persists_full_core_event_chain(session, mock_provider):
    workspace = get_or_create_default_workspace(session)

    result = run_daily_paper_trading_loop(session, mock_provider)

    events = session.exec(
        select(CoreEventLog).where(CoreEventLog.team_id == workspace.team.id).order_by(CoreEventLog.sequence)
    ).all()
    topics = [event.topic for event in events]

    assert result.status in {"completed", "skipped"}
    assert "market_event" in topics
    assert "strategy_input" in topics
    assert "trade_intent" in topics
    assert "risk_decision" in topics
    assert "order_state" in topics
    assert all(event.correlation_id for event in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api; python -m pytest tests/test_paper_trading_service.py::test_daily_paper_run_persists_full_core_event_chain -v`

Expected: FAIL because risk decision events are not persisted and skipped runs can have zero core events.

- [ ] **Step 3: Implement ledger enforcement**

Ensure automated daily paper runs persist all event envelopes from TradingEngine and persist risk decision records for every order. A skipped run because existing daily data already exists must still produce an audit event explaining the skip.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api; python -m pytest tests/test_paper_trading_service.py::test_daily_paper_run_persists_full_core_event_chain -v`

Expected: PASS.

### Task 4: Remove Paper Execution Bypass

**Files:**
- Modify: `apps/api/app/services/paper_trading.py`
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_paper_trading_service.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_manual_paper_order_requires_registered_strategy(client):
    response = client.post(
        "/api/mvp/paper-trading/orders",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1, "strategy_id": "missing_strategy"},
    )

    assert response.status_code == 400
    assert "Strategy is not registered for execution" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api; python -m pytest tests/test_mvp_routes.py::test_manual_paper_order_requires_registered_strategy -v`

Expected: FAIL because request schema does not carry strategy id and the route does not check registry.

- [ ] **Step 3: Implement execution route control**

Add `strategy_id` to manual paper orders with default `deterministic_watchlist_v1`, validate it through Strategy Control, and reject unknown strategies before order execution.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api; python -m pytest tests/test_mvp_routes.py::test_manual_paper_order_requires_registered_strategy -v`

Expected: PASS.

### Task 5: Runtime Verification

**Files:**
- No code changes unless tests expose defects.

- [ ] **Step 1: Run focused backend tests**

Run: `cd apps/api; python -m pytest tests/test_strategy_control.py tests/test_paper_trading_service.py tests/test_strategy_lifecycle.py tests/test_strategy_registry.py -v`

Expected: PASS.

- [ ] **Step 2: Run full backend tests**

Run: `cd apps/api; python -m pytest -v`

Expected: PASS.

- [ ] **Step 3: Verify Docker runtime event ledger is non-zero**

Run:

```powershell
docker compose exec -T postgres psql -U ai_stocks -d ai_stocks -c "select count(*) from coreeventlog;"
Invoke-RestMethod http://127.0.0.1:8000/api/mvp/paper-trading/event-ledger | ConvertTo-Json -Depth 8
```

Expected: `coreeventlog` count is greater than zero and API reports `replay_ready=true` for the latest non-skipped run or at least non-zero event count for the latest audited run.

---

### Self-Review

Spec coverage:
- Registry controls execution: Task 1 and Task 4.
- Lifecycle controls eligibility: Task 2 and Task 4.
- Event ledger non-zero runtime DB: Task 3 and Task 5.
- No execution bypass paths: Task 1, Task 3, Task 4.
- AI isolated from production path: no AI files are introduced into paper execution; route remains research-only.

Placeholder scan: no TODO/TBD placeholders.

Type consistency: `StrategyExecutionBinding`, `StrategyExecutionMode`, `get_strategy_execution_binding`, and `assert_strategy_execution_allowed` are introduced in Task 1 and reused consistently.
