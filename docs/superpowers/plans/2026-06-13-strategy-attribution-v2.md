# Strategy Attribution v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the read-only attribution layer so it can diagnose per-ticker signal quality, signal decay, expectancy components, and drawdown contributors.

**Architecture:** Keep `strategy_attribution.py` as the analytics boundary and keep the endpoint path unchanged. Extend the response model additively so existing UI and clients continue to work.

**Tech Stack:** FastAPI, SQLModel, Pydantic, Next.js, TypeScript, Playwright.

---

### Task 1: Backend Attribution v2 Models

**Files:**
- Modify: `apps/api/app/services/strategy_attribution.py`
- Modify: `apps/api/tests/test_strategy_attribution.py`

- [ ] Add failing tests for `ticker_diagnostics`, `signal_decay`, `expectancy_decomposition.components`, and `drawdown.contributors`.
- [ ] Run `python -m pytest tests/test_strategy_attribution.py -q` and verify the tests fail because the new fields do not exist.
- [ ] Add the minimal Pydantic models and aggregation helpers.
- [ ] Run `python -m pytest tests/test_strategy_attribution.py -q` and verify all attribution tests pass.

### Task 2: API Contract Coverage

**Files:**
- Modify: `apps/api/tests/test_mvp_routes.py`

- [ ] Extend the mocked `/api/mvp/strategy-lab/attribution` route test to include v2 fields.
- [ ] Run the route test and verify it passes.

### Task 3: Frontend Client and Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-lab-status-panel.tsx`
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] Extend the TypeScript attribution payload and validator for v2 fields.
- [ ] Add compact rows/chips to the attribution panel for ticker diagnostics, decay, components, and contributors.
- [ ] Extend the Strategy Lab Playwright test mock and assertions.
- [ ] Run the single Playwright test with `PLAYWRIGHT_PORT=3112 npx playwright test tests/mvp.spec.ts --grep "strategy lab renders readiness status"`.

### Task 4: Full Verification and Integration

**Files:**
- All changed files.

- [ ] Run `python -m pytest tests -q`.
- [ ] Run `npm run lint`.
- [ ] Run `npm run build`.
- [ ] Run `PLAYWRIGHT_PORT=3113 npx playwright test`.
- [ ] Commit the feature.
- [ ] Fast-forward merge into `master`.
- [ ] Restart Docker API and Web.
- [ ] Verify `GET http://127.0.0.1:8000/api/mvp/strategy-lab/attribution`.
