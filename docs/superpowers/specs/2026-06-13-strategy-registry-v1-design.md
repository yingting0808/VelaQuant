# Strategy Registry v1 Design

> **Scope:** Add a read-only Strategy Control Plane surface. Do not rewrite the trading core, paper execution path, risk engine, LEAN runner, or lifecycle system.

## Goal

Make the system answer one missing control-plane question:

- Which strategies does the platform know about, and which one is currently active in paper runtime?

This is a prerequisite for lifecycle management, but it is not lifecycle automation.

## Design

`Strategy Registry v1` exposes a single read-only aggregate:

```text
StrategyEvaluation
  + StrategyAttribution
  + LEAN catalog
  + latest LEAN backtest
  -> StrategyRegistryPayload
```

The registry creates two classes of entries:

- `paper_core`: the current deterministic paper strategy running through the event-driven trading core.
- `lean_catalog`: cataloged LEAN strategies that can be backtested, but are not connected to paper runtime.

## Ranking

The active paper strategy gets a conservative score from existing alpha diagnostics:

```text
score =
  stability_score * 0.40
  + signal_precision * 0.20
  + positive_expectancy_flag * 0.20
  + drawdown_score * 0.20
```

The score is displayed on a 0-100 scale. LEAN catalog strategies remain at `0` until they have a runtime evaluation path comparable to paper strategies.

## API Contract

`GET /api/mvp/strategy-lab/registry`

Returns:

- `active_strategy_id`
- ranked `entries`
- `missing_capabilities`
- read-only `summary`

`missing_capabilities` intentionally exposes the next gaps:

- `strategy_versioning_persistence`
- `multi_strategy_parallel_runtime`
- `strategy_competition_runtime`
- `hot_swap_execution_binding`
- `automatic_lifecycle_actions`

## UI Contract

The Strategy Lab status panel adds a `策略注册表` section showing:

- current active strategy
- rank and score
- source and execution mode
- promotion gate
- missing control-plane capabilities
- live/hot-swap support status

## Non-Goals

- No Strategy Lifecycle Manager.
- No automatic promotion or kill switch.
- No hot-swap execution binding.
- No live trading enablement.
- No claim that registry ranking is sufficient alpha proof.
