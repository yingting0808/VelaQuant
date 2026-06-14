# Paper Action Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only paper trading action plan that turns operations health, alpha gate progress, execution diagnostics, and risk profile into prioritized next actions.

**Architecture:** Compose existing read-only services; do not mutate strategy lifecycle, risk limits, orders, reviews, or event logs. Expose the plan through FastAPI and render it in the paper trading workspace.

**Tech Stack:** FastAPI, Pydantic, SQLModel, existing paper operations/execution/risk/alpha services, Next.js paper workspace.

---

### Task 1: Backend Service

**Files:**
- Create: `apps/api/app/services/paper_action_plan.py`
- Test: `apps/api/tests/test_paper_action_plan.py`

- [ ] Write failing tests for blocked ledger and collecting alpha cases.
- [ ] Implement action plan payloads and service composition.
- [ ] Run service tests.

### Task 2: API Route

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] Write failing route test for `GET /api/mvp/paper-trading/action-plan`.
- [ ] Add route.
- [ ] Run route test.

### Task 3: Frontend Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] Add client type, fallback, validator, and fetch function.
- [ ] Fetch action plan with paper workspace data.
- [ ] Render `行动计划` panel.
- [ ] Run paper workspace E2E.

### Task 4: Verification

Run backend tests, frontend build, Playwright, Docker route check, and browser panel read.
