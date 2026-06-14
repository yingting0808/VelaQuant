# Paper Simulation Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lab-only multi-day paper simulation runner that can create multiple audited daily paper runs without waiting for real calendar days.

**Architecture:** Keep production trading unchanged by adding an explicit `trading_day` parameter to the existing daily paper loop and by creating a separate simulation service and API route. Each simulated day still uses StrategyRegistry, the trading core, risk, execution, paper review, and event ledger; the service only supplies deterministic scenario quotes and dates.

**Tech Stack:** FastAPI, Pydantic, SQLModel, existing MarketDataProvider protocol, existing paper trading service, existing event ledger.

---

### Task 1: Daily Loop Trading-Day Injection

**Files:**
- Modify: `apps/api/app/services/paper_trading.py`
- Test: `apps/api/tests/test_paper_trading_service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_daily_run_accepts_explicit_trading_day_for_lab_simulation():
    with make_session() as session:
        provider = FixtureProvider()

        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-14")
        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-15")

        reviews = session.exec(select(PaperReview).order_by(PaperReview.trading_day)).all()
        runs = session.exec(select(PaperRun).order_by(PaperRun.trading_day)).all()
        assert [review.trading_day for review in reviews] == ["2026-06-14", "2026-06-15"]
        assert [run.trading_day for run in runs] == ["2026-06-14", "2026-06-15"]
        assert all(run.status == PaperRunStatus.completed for run in runs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_paper_trading_service.py::test_daily_run_accepts_explicit_trading_day_for_lab_simulation -q`
Expected: FAIL because `run_daily_paper_trading_loop` does not accept `trading_day`.

- [ ] **Step 3: Write minimal implementation**

Add optional `trading_day: str | None = None` to `run_daily_paper_trading_loop`, use `trading_day or _current_trading_day()`, pass the resolved day into `_create_review`, and update `_create_review` to persist that exact day.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_paper_trading_service.py::test_daily_run_accepts_explicit_trading_day_for_lab_simulation -q`
Expected: PASS.

### Task 2: Simulation Service

**Files:**
- Create: `apps/api/app/services/paper_simulation.py`
- Test: `apps/api/tests/test_paper_simulation.py`

- [ ] **Step 1: Write the failing test**

```python
def test_paper_simulation_runs_multiple_days_through_daily_loop():
    with make_session() as session:
        result = run_paper_simulation_lab(
            session,
            base_provider=FixtureProvider(),
            start_date=date(2026, 6, 14),
            days=3,
            scenario="bullish",
        )

        assert result.days_requested == 3
        assert result.days_completed == 3
        assert [item.trading_day for item in result.items] == ["2026-06-14", "2026-06-15", "2026-06-16"]
        assert result.review_day_count == 3
        assert result.event_chain_count > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_paper_simulation.py::test_paper_simulation_runs_multiple_days_through_daily_loop -q`
Expected: FAIL because `paper_simulation` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `PaperSimulationRequest`, `PaperSimulationItem`, `PaperSimulationPayload`, a scenario provider wrapper, and `run_paper_simulation_lab`. The service must call `run_daily_paper_trading_loop(..., trading_day=day)` once per day and then return review trend plus alpha validation facts.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_paper_simulation.py::test_paper_simulation_runs_multiple_days_through_daily_loop -q`
Expected: PASS.

### Task 3: API Route

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write the failing route test**

```python
def test_mvp_paper_simulation_route_runs_lab_window(monkeypatch):
    payload = PaperSimulationPayload(
        scenario="bullish",
        start_date="2026-06-14",
        days_requested=2,
        days_completed=2,
        review_day_count=2,
        consecutive_positive_expectancy_days=0,
        latest_expectancy=0,
        average_expectancy=0,
        event_chain_count=2,
        alpha_ready=False,
        blockers=["closed_trade_sample"],
        items=[],
        summary="fixture",
    )
    monkeypatch.setattr(mvp, "run_paper_simulation_lab", lambda session, base_provider, request: payload, raising=False)
    client = TestClient(create_app())

    response = client.post("/api/mvp/paper-trading/simulation/run", json={"days": 2, "scenario": "bullish"})

    assert response.status_code == 200
    assert response.json()["days_completed"] == 2
```

- [ ] **Step 2: Run route test to verify it fails**

Run: `python -m pytest tests/test_mvp_routes.py::test_mvp_paper_simulation_route_runs_lab_window -q`
Expected: FAIL because route and payload imports do not exist.

- [ ] **Step 3: Add route**

Import `PaperSimulationRequest` and `run_paper_simulation_lab`; add `POST /api/mvp/paper-trading/simulation/run` that uses the current provider and DB session.

- [ ] **Step 4: Run route test to verify it passes**

Run: `python -m pytest tests/test_mvp_routes.py::test_mvp_paper_simulation_route_runs_lab_window -q`
Expected: PASS.

### Task 4: Frontend Lab Control

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Write/update the frontend E2E expectation**

Add assertions that the paper trading page contains the lab simulation panel label `多日模拟` and a mock result summary after clicking `运行 5 日模拟`.

- [ ] **Step 2: Run Playwright test to verify it fails**

Run: `cmd /c "cd apps\web && set PLAYWRIGHT_PORT=3135&& npx playwright test tests/mvp.spec.ts -g 模拟盘 -q"`
Expected: FAIL because the panel is missing.

- [ ] **Step 3: Add client and UI**

Add `runPaperSimulationLab` to `client-api.ts`, add a compact `多日模拟` panel to `paper-trading-workspace.tsx`, and refresh report/trend/runs/ledger after simulation.

- [ ] **Step 4: Run Playwright test to verify it passes**

Run: `cmd /c "cd apps\web && set PLAYWRIGHT_PORT=3135&& npx playwright test tests/mvp.spec.ts -g 模拟盘 -q"`
Expected: PASS.

### Task 5: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Backend test suite**

Run: `python -m pytest -q` in `apps/api`.
Expected: all tests pass.

- [ ] **Step 2: Frontend build**

Run: `npm run build` in `apps/web`.
Expected: build succeeds.

- [ ] **Step 3: Frontend E2E**

Run: `cmd /c "cd apps\web && set PLAYWRIGHT_PORT=3136&& npx playwright test"`.
Expected: all tests pass.
