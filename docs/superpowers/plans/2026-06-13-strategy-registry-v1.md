# Strategy Registry v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Strategy Registry that exposes the current paper strategy and cataloged LEAN strategies as a control-plane view.

**Architecture:** Keep execution unchanged. Add a backend aggregation service, a FastAPI route, a typed frontend client contract, and a compact Strategy Lab panel.

**Tech Stack:** FastAPI, Pydantic, SQLModel, Next.js, TypeScript, Playwright.

---

### Task 1: Backend Registry Contract

**Files:**
- Add: `apps/api/app/services/strategy_registry.py`
- Add: `apps/api/tests/test_strategy_registry.py`
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/api/app/api/routes/mvp.py`

- [x] Write failing tests for paper strategy ranking and LEAN catalog entries.
- [x] Write route test for `GET /api/mvp/strategy-lab/registry`.
- [x] Implement `StrategyRegistryEntry` and `StrategyRegistryPayload`.
- [x] Aggregate evaluation, attribution, catalog, and latest backtest status.
- [x] Expose missing lifecycle/control-plane capabilities.
- [x] Run targeted backend tests and confirm they pass.

### Task 2: Frontend Registry Display

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-lab-status-panel.tsx`
- Modify: `apps/web/tests/mvp.spec.ts`

- [x] Add TypeScript payload types and offline fallback.
- [x] Add runtime payload validation.
- [x] Fetch registry data alongside status, evaluation, and attribution.
- [x] Render read-only registry, ranking score, source, execution mode, and missing capabilities.
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
