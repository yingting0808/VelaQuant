# Strategy Attribution Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only attribution layer that explains current paper-strategy behavior using existing event ledger, order, position, and review data.

**Architecture:** Keep attribution separate from Trading Core and Alpha Evaluation. Implement a backend service, expose it through `/api/mvp/strategy-lab/attribution`, and render a compact Strategy Lab panel.

**Tech Stack:** Python, SQLModel, Pydantic, FastAPI, pytest, Next.js, TypeScript, Playwright.

---

## File Structure

- Create `apps/api/app/services/strategy_attribution.py`: attribution payloads and read-only computation.
- Create `apps/api/tests/test_strategy_attribution.py`: backend attribution tests.
- Modify `apps/api/app/api/routes/mvp.py`: add attribution endpoint.
- Modify `apps/api/tests/test_mvp_routes.py`: API route test.
- Modify `apps/web/src/lib/client-api.ts`: attribution payload type, validator, fetch helper.
- Modify `apps/web/src/components/strategy-lab-status-panel.tsx`: render attribution panel.
- Modify `apps/web/tests/mvp.spec.ts`: Strategy Lab attribution panel coverage.

## Tasks

1. Write failing backend tests for empty data, event-log signal quality, false positives, and regime/drawdown proxy.
2. Implement `strategy_attribution.py`.
3. Add FastAPI endpoint and route test.
4. Add frontend client helper and panel.
5. Run backend tests, frontend typecheck/build, and Playwright.
6. Commit, merge, restart Docker API/Web, and verify the live endpoint.
