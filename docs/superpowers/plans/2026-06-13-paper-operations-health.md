# Paper Operations Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DB-backed operations health layer for the daily paper trading loop so the system can tell whether today's candidate generation, simulation, event ledger, and review pipeline ran cleanly and whether a retry is allowed.

**Architecture:** Keep trading decisions unchanged. Add a read-only service that derives health from `PaperRun`, `PaperReview`, and `CoreEventLog`, expose it through the existing FastAPI MVP router, and render it in the existing Paper Trading workspace. The service is an operations control plane, not a strategy engine.

**Tech Stack:** FastAPI, Pydantic, SQLModel, PostgreSQL/SQLite-compatible queries, existing Paper Trading service, existing Next/React frontend.

---

## Files

- Create: `apps/api/app/services/paper_operations.py`
- Create: `apps/api/tests/test_paper_operations.py`
- Modify: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/paper-trading-workspace.tsx`
- Modify: `apps/web/tests/mvp.spec.ts`

## Task 1: Backend Operations Status Service

- [ ] Write tests in `apps/api/tests/test_paper_operations.py`.
- [ ] Verify the tests fail because `app.services.paper_operations` does not exist.
- [ ] Implement `PaperOperationsStatusPayload` and `get_paper_operations_status(session)`.
- [ ] Verify targeted tests pass.

Required behavior:

- No runs today: `run_state="not_started"`, `can_retry_today=true`, blocker `daily_run_missing`.
- Today completed with review and event ledger records: `run_state="completed"`, `can_retry_today=false`, no blockers.
- Today failed without review: `run_state="failed"`, `can_retry_today=true`, blocker `latest_run_failed`.
- Latest completed run with no events: blocker `event_ledger_not_replayable`.

## Task 2: API Route

- [ ] Add route test in `apps/api/tests/test_mvp_routes.py` for `GET /api/mvp/paper-trading/operations`.
- [ ] Verify route test fails with 404.
- [ ] Import `get_paper_operations_status` in `apps/api/app/api/routes/mvp.py`.
- [ ] Add `paper_trading_operations_status()` route returning `.model_dump()`.
- [ ] Verify route test passes.

## Task 3: Frontend Client and Workspace

- [ ] Add `PaperOperationsStatusPayload` type, fallback, validator, and `getPaperOperationsStatus()` in `apps/web/src/lib/client-api.ts`.
- [ ] Update `PaperTradingWorkspace` to load operations status with summary/scheduler/runs/event ledger.
- [ ] Render a compact `运行健康` panel above `每日调度`.
- [ ] Ensure the panel shows run state, recommended action, blockers, retry availability, and event ledger status.

## Task 4: Frontend E2E

- [ ] Add Playwright route fixture for `/api/mvp/paper-trading/operations`.
- [ ] Assert the Paper Trading page shows `运行健康`, `completed`, `hold_until_next_session`, and `事件链可回放`.
- [ ] Verify the focused Playwright test passes.

## Task 5: Full Verification

- [ ] Run `python -m pytest -q` from `apps/api`.
- [ ] Run `npm run lint` from `apps/web`.
- [ ] Run `npm run build` from `apps/web`.
- [ ] Run `npx playwright test` from `apps/web` with a fresh `PLAYWRIGHT_PORT`.
- [ ] Restart Docker `api` and `web`.
- [ ] Verify `GET /health` and `GET /api/mvp/paper-trading/operations`.
- [ ] Verify `http://127.0.0.1:3000/paper-trading` displays the new operations panel in the in-app browser.
