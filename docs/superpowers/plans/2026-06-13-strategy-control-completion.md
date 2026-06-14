# Strategy Control Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the strategy control plane capabilities that were still marked NOT IMPLEMENTED: persisted strategy versions, rollback/hot-swap binding, multi-strategy runtime competition, and shadow/live-small account adapters.

**Architecture:** Keep the current FastAPI/Pydantic/SQLModel service shape. Strategies continue to enter execution through `StrategyRegistry -> StrategyEngine`; lifecycle gates determine which execution modes are allowed; paper/shadow/live-small use isolated simulated accounts before any future live adapter.

**Tech Stack:** FastAPI, Pydantic, SQLModel, APScheduler, Redis Streams, PostgreSQL, Redis, in-repo `apps/api/app/trading_core/` core.

---

### Task 1: Persist Strategy Versions and Active Binding

**Files:**
- Modify: `apps/api/app/domain/models.py`
- Modify: `apps/api/app/db/session.py`
- Create: `apps/api/app/services/strategy_versions.py`
- Test: `apps/api/tests/test_strategy_versions.py`

- [ ] **Step 1: Write failing tests**

```python
def test_strategy_version_registry_seeds_default_active_version():
    with make_session() as session:
        state = get_strategy_version_control(session)
        assert state.active_strategy_id == "deterministic_watchlist_v1"
        assert state.active_version == "v1"
        assert state.versions[0].is_active is True


def test_strategy_version_control_can_hot_swap_and_rollback():
    with make_session() as session:
        register_strategy_version(session, strategy_id="deterministic_watchlist_v1", version="v2", parameters_json='{"notional": 1000}')
        activate_strategy_version(session, strategy_id="deterministic_watchlist_v1", version="v2", reason="test hot swap")
        assert get_strategy_version_control(session).active_version == "v2"
        rollback_strategy_version(session, strategy_id="deterministic_watchlist_v1")
        assert get_strategy_version_control(session).active_version == "v1"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_strategy_versions.py -q`
Expected: FAIL because `app.services.strategy_versions` does not exist.

- [ ] **Step 3: Implement minimal persistence**

Add SQLModel tables for `StrategyVersionRecord` and `StrategyActiveBinding`, plus helpers to seed default `v1`, register `v2`, activate by version, and rollback to the previous active binding.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_strategy_versions.py -q`
Expected: PASS.

### Task 2: Wire Version Binding into Strategy Control

**Files:**
- Modify: `apps/api/app/services/strategy_control.py`
- Modify: `apps/api/app/services/strategy_registry.py`
- Modify: `apps/api/tests/test_strategy_control.py`
- Modify: `apps/api/tests/test_strategy_registry.py`

- [ ] **Step 1: Write failing tests**

```python
def test_execution_binding_uses_active_strategy_version_parameters():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        register_strategy_version(session, strategy_id="deterministic_watchlist_v1", version="v2", parameters_json='{"notional": 750}')
        activate_strategy_version(session, strategy_id="deterministic_watchlist_v1", version="v2", reason="test")
        binding = get_strategy_execution_binding(session, workspace.team.id, "deterministic_watchlist_v1")
        assert binding.version == "v2"
        assert binding.supports_hot_swap is True
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_strategy_control.py::test_execution_binding_uses_active_strategy_version_parameters -q`
Expected: FAIL because binding still hardcodes `v1`.

- [ ] **Step 3: Implement binding integration**

Read active version from `strategy_versions`, derive `notional` from version parameters unless an explicit order notional is supplied, and remove `strategy_versioning_persistence` plus `hot_swap_execution_binding` from registry missing capabilities.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_strategy_control.py tests/test_strategy_registry.py -q`
Expected: PASS.

### Task 3: Add Multi-Strategy Runtime Competition

**Files:**
- Create: `apps/api/app/services/strategy_runtime.py`
- Modify: `apps/api/app/services/strategy_registry.py`
- Test: `apps/api/tests/test_strategy_runtime.py`
- Modify: `apps/api/tests/test_strategy_registry.py`

- [ ] **Step 1: Write failing tests**

```python
def test_strategy_runtime_scores_multiple_registered_strategies():
    result = run_strategy_competition(
        strategies=[
            StrategyRuntimeCandidate(strategy_id="deterministic_watchlist_v1", version="v1", ranking_score=60, eligible=True),
            StrategyRuntimeCandidate(strategy_id="deterministic_watchlist_v1", version="v2", ranking_score=72, eligible=True),
        ]
    )
    assert result.winner.strategy_id == "deterministic_watchlist_v1"
    assert result.winner.version == "v2"
    assert result.entries[0].rank == 1
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_strategy_runtime.py -q`
Expected: FAIL because runtime service does not exist.

- [ ] **Step 3: Implement deterministic competition**

Add Pydantic models and pure ranking logic. Registry should expose competition status from actual registry entries and remove `multi_strategy_parallel_runtime` / `strategy_competition_runtime` once runtime can rank more than one executable version.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_strategy_runtime.py tests/test_strategy_registry.py -q`
Expected: PASS.

### Task 4: Add Shadow and Live-Small Simulated Account Adapters

**Files:**
- Modify: `apps/api/app/domain/models.py`
- Create: `apps/api/app/services/execution_accounts.py`
- Modify: `apps/api/app/services/strategy_lifecycle.py`
- Test: `apps/api/tests/test_execution_accounts.py`
- Modify: `apps/api/tests/test_strategy_lifecycle.py`

- [ ] **Step 1: Write failing tests**

```python
def test_execution_accounts_create_isolated_shadow_and_live_small_accounts():
    with make_session() as session:
        accounts = get_or_create_strategy_execution_accounts(session, team_id=uuid4(), strategy_id="deterministic_watchlist_v1")
        assert [account.mode for account in accounts] == ["paper", "shadow", "live_small"]
        assert accounts[1].cash == 100000.0
        assert accounts[2].cash == 5000.0
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_execution_accounts.py -q`
Expected: FAIL because execution account service does not exist.

- [ ] **Step 3: Implement account adapters and lifecycle awareness**

Extend paper account mode enum to include `shadow` and `live_small`, seed isolated accounts per strategy/mode, and remove lifecycle missing capabilities once adapters exist.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_execution_accounts.py tests/test_strategy_lifecycle.py -q`
Expected: PASS.

### Task 5: Full Verification

**Files:**
- No new files.

- [ ] Run: `python -m pytest -q` in `apps/api`
- [ ] Run: `npm run build` in `apps/web`
- [ ] Run: `docker compose restart api`
- [ ] Verify: `GET http://127.0.0.1:8000/health`
- [ ] Verify strategy registry, lifecycle, scheduler, and Redis stream via runtime API/DB.
