# Strategy Attribution v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Strategy Attribution Layer with volatility PnL decomposition and regime-level risk-adjusted diagnostics.

**Architecture:** Keep the existing `strategy_attribution.py` service as the single attribution boundary. Add stable payload fields, then surface them through the existing FastAPI route and Strategy Lab panel.

**Tech Stack:** FastAPI, Pydantic, SQLModel, Next.js, TypeScript, Playwright.

---

### Task 1: Backend Attribution Contract

**Files:**
- Modify: `apps/api/app/services/strategy_attribution.py`
- Test: `apps/api/tests/test_strategy_attribution.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [x] Write failing tests for `volatility_component`, `sample_count`, and `sharpe_proxy`.
- [x] Run targeted tests and confirm they fail on missing model fields/components.
- [x] Add `volatility_component` to `AttributionComponent`.
- [x] Add `sample_count` and `sharpe_proxy` to `RegimePerformanceItem`.
- [x] Compute `sharpe_proxy` from price-history returns using a 1% volatility floor.
- [x] Feed high-volatility observed PnL into `volatility_component`.
- [x] Run targeted backend tests and confirm they pass.

### Task 2: Frontend Contract and Display

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-lab-status-panel.tsx`
- Test: `apps/web/tests/mvp.spec.ts`

- [x] Add TypeScript contract fields for `volatility_component`, `sample_count`, and `sharpe_proxy`.
- [x] Add fallback payload values for offline mode.
- [x] Validate new fields in the API payload guard.
- [x] Render volatility component and primary regime `sharpe_proxy`.
- [x] Update Strategy Lab E2E expectations.
- [x] Run targeted Playwright Strategy Lab tests and confirm they pass.

### Task 3: Verification

**Files:**
- Verify: `apps/api`
- Verify: `apps/web`

- [ ] Run full backend test suite.
- [ ] Run frontend type check.
- [ ] Run frontend production build.
- [ ] Run full Playwright suite.
- [ ] Commit and merge back to `master`.

