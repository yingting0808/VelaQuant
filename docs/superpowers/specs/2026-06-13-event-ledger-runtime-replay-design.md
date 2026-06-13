# Event Ledger Runtime + Replay Design

> **Scope:** Make CoreEventLog observable and replayable from the paper-trading runtime. Do not change strategy decisions, risk rules, execution state transitions, or broker behavior.

## Goal

Close the runtime audit gap:

- Paper runtime already persists core events when a non-skipped run generates candidates/orders.
- Users still need a reliable status surface that explains whether the latest run has replayable events.
- Users need a compact replay chain grouped by `correlation_id`.

## Runtime Behavior

Existing paper trading writes these event topics into `CoreEventLog`:

- `market_event`
- `strategy_input`
- `trade_intent`
- `order_state`

For same-day idempotency, a second run can be `skipped`. A skipped latest run may have zero events even though older completed runs have replayable events. The status API must make that distinction visible.

## Replay Model

`EventLedgerReplay` groups latest-run events by `correlation_id`.

Each chain exposes:

- `ticker`
- ordered `topics`
- ordered `order_states`
- `terminal_state`
- `event_count`

This allows the UI to show the real chain:

```text
market_event -> strategy_input -> trade_intent -> order_state...
```

and the order state sequence:

```text
new -> validated -> risk_approved -> sent -> filled
```

## API Contract

`GET /api/mvp/paper-trading/event-ledger`

Returns:

- total event count for the workspace
- latest run id/status
- latest run event count
- latest topic counts
- latest correlation count
- replay readiness
- warnings
- latest replay payload when available

Warnings include:

- `no_paper_runs`
- `missing_core_events`
- `latest_run_has_no_events`

## UI Contract

The Paper Trading workspace adds an `事件账本` panel showing:

- replay-ready status
- total events
- latest-run events
- correlation count
- selected chain ticker and terminal state
- topic counts
- order state sequence
- warnings

## Non-Goals

- No event-sourced portfolio reconstruction.
- No cross-run replay timeline.
- No order repair or re-execution.
- No broker event ingestion.
