# Paper Daily Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the paper trading daily loop idempotent and schedulable in Docker.

**Architecture:** Use `PaperReview.trading_day` as the same-day guard and APScheduler as the mature cron runner. The scheduler calls the existing paper trading service rather than creating a second execution path.

**Tech Stack:** Python, FastAPI lifespan, APScheduler, SQLModel, pytest, Docker Compose.

---

## Tasks

- [ ] Add a failing service test proving repeated same-day daily runs do not create extra orders or reviews.
- [ ] Add a `PaperReview` day check to `run_daily_paper_trading_loop`.
- [ ] Add APScheduler dependency and scheduler service with start, shutdown, run-once, and status functions.
- [ ] Add tests for disabled and enabled scheduler configuration.
- [ ] Add a scheduler status API route.
- [ ] Enable scheduler in Docker Compose through environment variables.
- [ ] Run focused tests and full API tests.

