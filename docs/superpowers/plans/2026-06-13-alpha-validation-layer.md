# Alpha Validation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an alpha validation layer that uses real paper trading runs, reviews, orders, closed trades, expectancy, and drawdown to decide whether the strategy has enough stable paper evidence for lifecycle promotion.

**Architecture:** Keep AI out of the execution path. `AlphaValidation` reads storage facts only, outputs validation status and blockers, and feeds lifecycle gates; StrategyRegistry/StrategyEngine/ExecutionEngine remain the execution path.

**Tech Stack:** FastAPI, Pydantic, SQLModel, PostgreSQL, Redis Streams, APScheduler, Next.js.

---

### Task 1: Alpha Validation Service

**Files:**
- Create: `apps/api/app/services/alpha_validation.py`
- Test: `apps/api/tests/test_alpha_validation.py`

- [ ] **Step 1: Write failing tests**

```python
def test_alpha_validation_blocks_without_consecutive_positive_reviews():
    payload = build_alpha_validation(
        reviews=[
            _review("2026-06-10", expectancy=1.2, equity=100200),
            _review("2026-06-11", expectancy=-0.5, equity=100100),
            _review("2026-06-12", expectancy=1.1, equity=100350),
        ],
        orders=_orders(filled=12, closed=4),
        event_chain_count=120,
    )
    assert payload.alpha_ready is False
    assert payload.consecutive_positive_expectancy_days == 1
    assert "consecutive_positive_expectancy" in payload.blockers
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_alpha_validation.py -q`
Expected: FAIL because `alpha_validation` does not exist.

- [ ] **Step 3: Implement minimal service**

Add Pydantic payloads, pure `build_alpha_validation(...)`, and DB-backed `get_alpha_validation(session)`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_alpha_validation.py -q`
Expected: PASS.

### Task 2: Lifecycle Integration

**Files:**
- Modify: `apps/api/app/services/strategy_lifecycle.py`
- Test: `apps/api/tests/test_strategy_lifecycle.py`

- [ ] **Step 1: Write failing test**

```python
def test_lifecycle_blocks_promotion_when_alpha_validation_is_not_ready():
    payload = build_strategy_lifecycle(_paper_ready_evaluation(), alpha_ready=False)
    assert payload.can_promote is False
    assert payload.recommended_action == "continue_collecting_samples"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_strategy_lifecycle.py::test_lifecycle_blocks_promotion_when_alpha_validation_is_not_ready -q`
Expected: FAIL because lifecycle does not accept alpha validation.

- [ ] **Step 3: Implement lifecycle gate**

Add alpha validation as a required gate for promotion while keeping automatic kill on negative expectancy.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_strategy_lifecycle.py -q`
Expected: PASS.

### Task 3: API and Frontend Display

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-lab-status-panel.tsx`

- [ ] **Step 1: Write failing API test**

```python
def test_mvp_strategy_lab_alpha_validation_route_returns_gate():
    response = client.get("/api/mvp/strategy-lab/alpha-validation")
    assert response.status_code == 200
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_mvp_routes.py::test_mvp_strategy_lab_alpha_validation_route_returns_gate -q`
Expected: FAIL with 404.

- [ ] **Step 3: Implement API and frontend client**

Expose `GET /api/mvp/strategy-lab/alpha-validation` and render validation state in Strategy Lab.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_mvp_routes.py -q` and `npm run build`.

### Task 4: Runtime Verification

**Files:**
- No new files.

- [ ] Run `python -m pytest -q`
- [ ] Run `npm run build`
- [ ] Restart Docker API/Web
- [ ] Verify `GET /api/mvp/strategy-lab/alpha-validation`
- [ ] Verify `/strategy-lab` contains Alpha Validation output
