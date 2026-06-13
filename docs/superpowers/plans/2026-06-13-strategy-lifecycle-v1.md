# Strategy Lifecycle v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Lifecycle Manager that turns paper strategy evaluation into stage and gate recommendations.

**Architecture:** Keep execution unchanged. Add a lifecycle aggregation service, FastAPI route, typed frontend client contract, and a compact Strategy Lab lifecycle panel.

**Tech Stack:** FastAPI, Pydantic, SQLModel, Next.js, TypeScript, Playwright.

---

### Task 1: Backend Lifecycle Contract

**Files:**
- Add: `apps/api/app/services/strategy_lifecycle.py`
- Add: `apps/api/tests/test_strategy_lifecycle.py`
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/api/app/api/routes/mvp.py`

- [x] Write failing tests for shadow eligibility, event-ledger blocking, and kill review.
- [x] Write route test for `GET /api/mvp/strategy-lab/lifecycle`.
- [x] Implement lifecycle payload and rule models.
- [x] Compute stage recommendations from existing `StrategyEvaluationPayload`.
- [x] Keep `auto_actions_enabled=false`.
- [x] Run targeted backend tests and confirm they pass.

### Task 2: Frontend Lifecycle Display

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-lab-status-panel.tsx`
- Modify: `apps/web/tests/mvp.spec.ts`

- [x] Add TypeScript lifecycle contract and offline fallback.
- [x] Add runtime payload validation.
- [x] Fetch lifecycle data alongside status, evaluation, attribution, and registry.
- [x] Render lifecycle stage, recommended action, auto-action status, gate rules, and missing capabilities.
- [x] Update Strategy Lab E2E expectations.
- [x] Run targeted Playwright Strategy Lab test and confirm it passes on a fresh port.

### Task 3: Verification

**Files:**
- Verify: `apps/api`
- Verify: `apps/web`

- [x] Run full backend test suite.
- [x] Run frontend lint.
- [x] Run frontend production build.
- [x] Run full Playwright suite on a fresh port.
- [ ] Commit, merge into `master`, restart Docker, and verify the live endpoint.
