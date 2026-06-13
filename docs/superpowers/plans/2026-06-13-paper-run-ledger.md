# Paper Run Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist daily paper-trading run attempts and expose recent run history for operations review.

**Architecture:** Add SQLModel ledger tables for paper runs first, then route the daily loop and scheduler through that ledger. Keep core event-log table in the schema for the next event-capture phase, but do not wire it to every execution path until the run ledger is stable.

**Tech Stack:** Python 3.12, SQLModel, Pydantic, FastAPI, pytest.

---

### Task 1: Add Ledger Models

**Files:**
- Modify: `apps/api/app/domain/models.py`
- Modify: `apps/api/app/db/session.py`
- Test: `apps/api/tests/test_domain_models.py`

- [ ] Write failing tests that persist `PaperRun` and `CoreEventLog`.
- [ ] Run `python -m pytest tests/test_domain_models.py -q` from `apps/api` and confirm the new tests fail because the models do not exist.
- [ ] Add `PaperRunTrigger`, `PaperRunStatus`, `PaperRun`, and `CoreEventLog`.
- [ ] Extend schema compatibility in `app/db/session.py` for these tables through normal `SQLModel.metadata.create_all()`.
- [ ] Re-run `python -m pytest tests/test_domain_models.py -q` from `apps/api` and confirm it passes.
- [ ] Commit the model changes.

### Task 2: Record Daily Runs

**Files:**
- Modify: `apps/api/app/services/paper_trading.py`
- Modify: `apps/api/app/services/paper_scheduler.py`
- Test: `apps/api/tests/test_paper_trading_service.py`
- Test: `apps/api/tests/test_paper_scheduler.py`

- [ ] Write failing tests proving daily-run records `completed`, same-day reruns record `skipped`, and scheduler calls use `scheduled`.
- [ ] Run focused tests and confirm they fail on missing run ledger behavior.
- [ ] Add `PaperRunPayload`, `list_paper_runs()`, and `trigger` support for `run_daily_paper_trading_loop()`.
- [ ] Ensure failed runs are marked `failed` before re-raising.
- [ ] Re-run focused tests and confirm they pass.
- [ ] Commit service changes.

### Task 3: Expose Run History API

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] Write failing route test for `GET /api/mvp/paper-trading/runs`.
- [ ] Run the route test and confirm it fails before the endpoint exists.
- [ ] Add the endpoint and return recent run payloads.
- [ ] Re-run the route test and focused paper tests.
- [ ] Commit API changes.

### Task 4: Verification And Merge

**Files:**
- Existing backend suite.

- [ ] From `apps/api`, run `python -m pytest tests/test_paper_trading_service.py tests/test_paper_scheduler.py tests/test_mvp_routes.py -q`.
- [ ] From `apps/api`, run `python -m pytest tests -q`.
- [ ] Merge to `master` with fast-forward only.
- [ ] Restart Docker API and verify `/health`, `/api/mvp/paper-trading/scheduler`, `/api/mvp/paper-trading/daily-run`, and `/api/mvp/paper-trading/runs`.
