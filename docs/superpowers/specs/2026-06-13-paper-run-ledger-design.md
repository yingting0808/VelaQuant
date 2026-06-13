# Paper Run Ledger Design

## Goal

Make the daily paper-trading loop operationally auditable. Each scheduled or manual daily run should create a durable run ledger that records whether the run executed, why it skipped, which summary it produced, and the core trading events that explain strategy and execution behavior.

## Current Context

The system can already:

- run a daily paper loop through `run_daily_paper_trading_loop()`;
- keep same-day runs idempotent through `PaperReview.trading_day`;
- submit simulated orders through `ExecutionEngine` and `RiskEngine`;
- expose core event chains from `/api/mvp/trading-core/dry-run`;
- show scheduler health through `/api/mvp/paper-trading/scheduler`.

The missing piece is a persistent operations ledger. Today, if a scheduled run fires, the system has no first-class record of the run attempt itself. Reviews and orders show portfolio outcomes, but not whether the scheduler ran, skipped because the day was already reviewed, failed, or produced a particular event chain.

## Recommended Approach

Add a database-backed paper run ledger and core event log.

Use SQLModel tables:

- `PaperRun`: one row per daily-run attempt, manual or scheduled.
- `CoreEventLog`: one row per captured trading-core event envelope, optionally linked to a `PaperRun`.

Keep this phase synchronous and database-local. Do not introduce Redis Streams, Kafka, or background workers yet. The scheduler is already single-process and APScheduler-based; a durable SQL ledger gives enough reliability for the next development stage while keeping the system inspectable.

## Data Model

`PaperRun` stores:

- `account_id`, `team_id`, `trading_day`
- `trigger`: `manual` or `scheduled`
- `status`: `started`, `completed`, `skipped`, or `failed`
- counts for candidates, orders, positions
- `review_id` when a review exists
- `error_message` for failures
- `started_at`, `finished_at`

`CoreEventLog` stores:

- `run_id` when the event belongs to a paper run
- event ids, topic, sequence, correlation, causation
- `payload_json`
- `published_at`

## Service Behavior

`run_daily_paper_trading_loop()` should accept a trigger with default `manual`.

When called:

1. Create a `PaperRun` with `started`.
2. If the trading day already has a review, mark the run `skipped`, mark positions to market, and return the existing summary.
3. Otherwise generate candidates, auto-submit the top candidate, mark positions, create review, and mark the run `completed`.
4. If an exception occurs after the run row is created, mark the run `failed` and store the error before re-raising.

Manual order submission remains separate from daily-run attempts in this phase, but core order state remains persisted on `PaperOrder`.

## API Behavior

Add:

- `GET /api/mvp/paper-trading/runs`

The endpoint returns recent run ledgers ordered newest first, including trigger, status, trading day, counts, review id, error message, and timestamps.

Keep `/paper-trading/summary` focused on portfolio state. Do not overload it with operational history.

## Acceptance Criteria

- Daily-run creates a `PaperRun` row with `completed`.
- A second same-day daily-run creates a `PaperRun` row with `skipped` and does not duplicate orders.
- Scheduled runs pass `trigger=scheduled`.
- Failures during a run mark the current `PaperRun` as `failed`.
- API exposes recent run history.
- Existing paper trading behavior and full API tests remain passing.
