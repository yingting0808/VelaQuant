# Strategy Lifecycle v1 Design

> **Scope:** Add a read-only Strategy Lifecycle Manager. Do not automate promotion, killing, hot swapping, broker routing, or live execution.

## Goal

Make the system answer the next control-plane question:

- Should the current paper strategy remain in paper, move to shadow review, or enter kill review?

This creates the paper-to-shadow gate without changing the trading core.

## Lifecycle Stages

The stable stage vocabulary is:

- `paper`
- `shadow_candidate`
- `shadow`
- `live_small`
- `live`
- `killed`

v1 always reports the current deterministic runtime as `paper`. It may recommend `shadow_candidate` or `killed`, but it never mutates state.

## Gate Rules

The paper-to-shadow review gate checks:

- `minimum_filled_orders`: at least 30 filled paper orders.
- `positive_expectancy`: observed expectancy must be positive.
- `drawdown_limit`: max drawdown must be at or below 15%.
- `event_ledger_populated`: CoreEventLog must have runtime events.
- `closed_trade_sample`: at least 10 closed trades, so exits can be inspected.

All rules are reported as explicit rows with:

- `passed`
- `severity`
- `actual`
- `required`
- `message`

## Decisions

The decision logic is intentionally conservative:

- `negative_expectancy` -> `kill_review`, recommended stage `killed`, no automatic action.
- `paper_ready` with empty event ledger -> `repair_event_ledger`, stays `paper`.
- `paper_ready` with all blockers passing -> `eligible_for_shadow_review`, recommended stage `shadow_candidate`.
- `watch` -> `keep_paper_running`.
- `insufficient_sample` -> `continue_collecting_samples`.

## API Contract

`GET /api/mvp/strategy-lab/lifecycle`

Returns:

- current and recommended lifecycle stages
- recommended action
- promotion gate status
- promotion/kill booleans
- auto-action status
- gate rules
- missing lifecycle capabilities

## Non-Goals

- No lifecycle state persistence.
- No automatic promotion.
- No automatic kill switch.
- No shadow account adapter.
- No live-small or live broker adapter.
