# Paper Daily Automation Design

## Objective

Make the paper trading loop safe to run every day in Docker without manually babysitting it.

This phase adds two guarantees:

- the same trading day is idempotent, so repeated triggers do not keep buying;
- Docker can enable a mature scheduler to run the paper loop on a cron schedule.

## Scope

In scope:

- same-day idempotency using the existing `PaperReview.trading_day` record;
- APScheduler-based background scheduling;
- Docker Compose configuration to enable the scheduler;
- scheduler status API for visibility.

Out of scope:

- live broker routing;
- exchange calendar integration;
- distributed locking across multiple API replicas;
- front-end scheduler controls.

## Behavior

`POST /api/mvp/paper-trading/daily-run` now checks whether the default paper account already has a `PaperReview` for the current UTC trading day. If it exists, the service refreshes marks to market and returns the current summary without regenerating candidates or submitting new simulated orders.

When enabled, the API process starts APScheduler with one job:

```text
paper_trading_daily_run
```

The job calls the same `run_daily_paper_trading_loop` service used by the manual route, so scheduled and manual paths cannot diverge.

## Docker Defaults

Docker Compose enables the scheduler with:

```text
AI_STOCKS_PAPER_SCHEDULER_ENABLED=true
AI_STOCKS_PAPER_SCHEDULER_CRON=30 6 * * *
AI_STOCKS_PAPER_SCHEDULER_TIMEZONE=Asia/Shanghai
```

This means the local Docker API will attempt one daily paper run at 06:30 Asia/Shanghai time.

## Visibility

`GET /api/mvp/paper-trading/scheduler` returns:

- enabled flag;
- running flag;
- registered job count;
- cron expression;
- timezone.

