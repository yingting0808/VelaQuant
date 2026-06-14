# Paper Risk Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose current paper trading risk limits and exit rules so operators can understand why orders are approved, rejected, or auto-exited.

**Architecture:** Add a read-only FastAPI service that returns the current hard risk profile from the existing paper trading constants and risk limits. Render it in the paper trading workspace near execution diagnostics; no runtime risk behavior changes.

**Tech Stack:** FastAPI, Pydantic, existing trading core `RiskLimits`, existing Next.js workspace UI.

---

### Task 1: Backend Service

**Files:**
- Create: `apps/api/app/services/paper_risk_profile.py`
- Test: `apps/api/tests/test_paper_risk_profile.py`

- [ ] Write failing tests for default risk values and exit rules.
- [ ] Implement payload and `get_paper_risk_profile`.
- [ ] Run service tests.

### Task 2: API Route

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] Write failing route test for `GET /api/mvp/paper-trading/risk-profile`.
- [ ] Add route and imports.
- [ ] Run route test.

### Task 3: Frontend Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] Add type, fallback, validator, and fetch client.
- [ ] Fetch risk profile with the paper workspace data set.
- [ ] Render a compact `风险配置` panel.
- [ ] Run paper workspace E2E.

### Task 4: Verification

Run `python -m pytest -q`, `npm run build`, `npx playwright test`, and a Docker API route check.
