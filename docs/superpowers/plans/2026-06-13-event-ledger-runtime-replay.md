# Event Ledger Runtime + Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface runtime CoreEventLog health and latest-run replay chains in the paper trading workflow.

**Architecture:** Keep the existing paper runtime event writes. Add a read-only ledger service, FastAPI route, typed frontend client contract, and a Paper Trading UI panel.

**Tech Stack:** FastAPI, Pydantic, SQLModel, Next.js, TypeScript, Playwright.

---

### Task 1: Backend Ledger Status and Replay

**Files:**
- Add: `apps/api/app/services/event_ledger.py`
- Modify: `apps/api/tests/test_paper_trading_service.py`
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/api/app/api/routes/mvp.py`

- [x] Write failing tests for completed-run replay chain.
- [x] Write failing test for skipped latest run with older persisted events.
- [x] Write route test for `GET /api/mvp/paper-trading/event-ledger`.
- [x] Implement `EventLedgerStatus`, `EventLedgerReplay`, and chain grouping.
- [x] Expose warnings for no runs, missing events, and latest skipped/no-event runs.
- [x] Run targeted backend tests and confirm they pass.

### Task 2: Frontend Ledger Panel

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Modify: `apps/web/tests/mvp.spec.ts`

- [x] Add TypeScript ledger payload types and offline fallback.
- [x] Add runtime payload validation.
- [x] Fetch event ledger with paper summary and run list.
- [x] Refresh ledger after daily run and manual paper order.
- [x] Render replay-ready status, topic counts, order state sequence, and warnings.
- [x] Update Paper Trading E2E expectations and confirm targeted Playwright passes.

### Task 3: Verification

**Files:**
- Verify: `apps/api`
- Verify: `apps/web`

- [x] Run full backend test suite.
- [x] Run frontend lint.
- [x] Run frontend production build.
- [x] Run full Playwright suite on a fresh port.
- [ ] Commit, merge into `master`, restart Docker, and verify the live endpoint/page.
