# Strategy Regime Breakdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add market-history-driven regime breakdown to Strategy Attribution.

**Architecture:** Extend `strategy_attribution.py` with optional `MarketDataProvider` input. Route the existing API endpoint through `get_market_data_provider`, and extend the compact Strategy Lab attribution panel with the new breakdown.

**Tech Stack:** FastAPI, SQLModel, Pydantic, Next.js, TypeScript, Playwright.

---

### Task 1: Backend Regime Breakdown

**Files:**
- Modify: `apps/api/app/services/strategy_attribution.py`
- Modify: `apps/api/tests/test_strategy_attribution.py`

- [ ] Write failing tests for trend, range, high-volatility, and insufficient-data regime classification.
- [ ] Run `python -m pytest tests/test_strategy_attribution.py -q` and verify the new tests fail because `regime_breakdown` does not exist.
- [ ] Add `RegimeBreakdownPayload` and classification helpers.
- [ ] Run `python -m pytest tests/test_strategy_attribution.py -q` and verify all attribution tests pass.

### Task 2: API Contract

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/tests/test_mvp_routes.py`

- [ ] Pass `MarketDataProvider` into `attribute_current_paper_strategy`.
- [ ] Extend the route test for `regime_breakdown`.
- [ ] Run the route test.

### Task 3: Frontend Contract and Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-lab-status-panel.tsx`
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] Extend TypeScript types, fallback payload, and runtime validator.
- [ ] Render the leading regime breakdown row.
- [ ] Extend the Strategy Lab Playwright test.

### Task 4: Verification and Merge

- [ ] Run `python -m pytest tests -q`.
- [ ] Run `npm run lint`.
- [ ] Run `npm run build`.
- [ ] Run `PLAYWRIGHT_PORT=3114 npx playwright test`.
- [ ] Commit, merge to master, restart Docker API/Web, and verify the live endpoint.
