# Alpha Validation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative strategy evaluation service and Strategy Lab panel that reports whether the current paper strategy has enough evidence for promotion.

**Architecture:** Implement a read-only backend service over paper trading tables, expose it via `/api/mvp/strategy-lab/evaluation`, then show the result in the Strategy Lab status area.

**Tech Stack:** Python, SQLModel, FastAPI, pytest, Next.js, TypeScript, Playwright.

---

## File Structure

- Create `apps/api/app/services/strategy_evaluation.py`: read-only evaluator and response models.
- Create `apps/api/tests/test_strategy_evaluation.py`: unit tests for metrics and readiness classification.
- Modify `apps/api/app/api/routes/mvp.py`: add evaluation endpoint.
- Modify `apps/api/tests/test_mvp_routes.py`: route coverage.
- Modify `apps/web/src/lib/client-api.ts`: add client type and fetch helper.
- Modify `apps/web/src/components/strategy-lab-status-panel.tsx`: render evaluation panel.
- Modify `apps/web/tests/mvp.spec.ts`: assert evaluation panel renders.

## Tasks

1. Write failing backend tests for no-data, seeded paper data, drawdown, and paper-ready classification.
2. Implement `strategy_evaluation.py`.
3. Add FastAPI endpoint and route test.
4. Add frontend API helper and Strategy Lab panel.
5. Run backend tests, frontend lint/build, and targeted Playwright.
6. Commit and merge.
