# Alpha Gate Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured Alpha Gate progress so the system can explain how far paper trading is from validation thresholds.

**Architecture:** Build a read-only service on top of the existing `get_alpha_validation` facts and validation constants. Expose a FastAPI route and show a compact panel in the paper trading workspace; no lifecycle promotion or risk behavior changes.

**Tech Stack:** FastAPI, Pydantic, SQLModel, existing alpha validation service, existing Next.js paper workspace.

---

### Task 1: Backend Service

**Files:**
- Create: `apps/api/app/services/alpha_gate_progress.py`
- Test: `apps/api/tests/test_alpha_gate_progress.py`

- [ ] Write failing test from fixture reviews/orders/events.
- [ ] Implement gate item payloads and `get_alpha_gate_progress`.
- [ ] Run service tests.

### Task 2: API Route

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] Write failing route test for `GET /api/mvp/strategy-lab/alpha-gates`.
- [ ] Add route.
- [ ] Run route test.

### Task 3: Frontend Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] Add client type, fallback, validator, and fetch function.
- [ ] Fetch alpha gate progress with paper workspace data.
- [ ] Render `Alpha 门禁` panel.
- [ ] Run paper workspace E2E.

### Task 4: Verification

Run backend tests, frontend build, Playwright, Docker route check, and browser panel read.
