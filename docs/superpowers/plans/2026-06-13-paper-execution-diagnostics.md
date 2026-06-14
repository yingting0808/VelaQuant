# Paper Execution Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper execution diagnostics layer that explains filled/rejected orders, sell-side closed trade count, realized PnL, and risk rejection reasons.

**Architecture:** Create a read-only service that queries persisted `PaperOrder` rows for the current team and summarizes execution quality. Expose it through FastAPI and render it in the paper trading workspace; do not change StrategyRegistry, AI, broker execution, or risk rules.

**Tech Stack:** FastAPI, Pydantic, SQLModel, existing paper trading domain models, existing Next.js workspace UI.

---

### Task 1: Backend Service

**Files:**
- Create: `apps/api/app/services/paper_execution_diagnostics.py`
- Test: `apps/api/tests/test_paper_execution_diagnostics.py`

- [ ] **Step 1: Write failing tests** for empty state and mixed filled/rejected orders.
- [ ] **Step 2: Run tests** and verify import/service failures.
- [ ] **Step 3: Implement payload models and `get_paper_execution_diagnostics`.
- [ ] **Step 4: Run service tests** and verify pass.

### Task 2: API Route

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write failing route test** for `GET /api/mvp/paper-trading/execution-diagnostics`.
- [ ] **Step 2: Add route** that returns service payload.
- [ ] **Step 3: Run route test** and verify pass.

### Task 3: Frontend Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Extend E2E mock and assertions** for an `执行诊断` panel.
- [ ] **Step 2: Add client type, validator, fallback, and fetch function.
- [ ] **Step 3: Add compact diagnostics panel to the paper workspace.
- [ ] **Step 4: Run Playwright test** and verify pass.

### Task 4: Verification

**Files:**
- No new files.

- [ ] **Step 1:** `python -m pytest -q` in `apps/api`.
- [ ] **Step 2:** `npm run build` in `apps/web`.
- [ ] **Step 3:** `npx playwright test` in `apps/web`.
- [ ] **Step 4:** Docker API route check against `http://127.0.0.1:8000`.
