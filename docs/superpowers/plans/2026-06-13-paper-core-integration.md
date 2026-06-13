# Paper Core Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all paper trading orders through Trading Core risk and execution state-machine logic, then persist the audit trail.

**Architecture:** Extend paper order persistence with core audit fields, convert paper order requests into `TradeIntent` plus `PortfolioState`, and reuse `submit_paper_order` from the daily loop for automated paper simulation. Keep the implementation paper-only and deterministic.

**Tech Stack:** Python, SQLModel, Pydantic, pytest, existing FastAPI routes.

---

## File Structure

- Modify `apps/api/app/domain/models.py`: add Trading Core audit fields to `PaperOrder`.
- Modify `apps/api/app/services/paper_trading.py`: convert order execution to Trading Core and expose audit fields.
- Modify `apps/api/tests/test_paper_trading_service.py`: add red-green tests for core state persistence, risk rejection, and daily auto-submit.
- Add design and plan docs under `docs/superpowers/`.

## Tasks

- [ ] Write failing tests for core audit fields on filled paper buy orders.
- [ ] Write failing tests for risk-rejected paper orders that do not mutate cash or positions.
- [ ] Write failing tests for daily auto-submit creating audited simulated orders.
- [ ] Add nullable core fields to `PaperOrder` and payload model.
- [ ] Build helper functions for paper `PortfolioState`, `TradeIntent`, risk limits, and state history serialization.
- [ ] Route `submit_paper_order` through `ExecutionEngine`.
- [ ] Update daily loop to submit top candidates through `submit_paper_order`.
- [ ] Run focused paper tests and full API tests.

