# Trading System Readiness

## Goal

Add a read-only daily readiness view that summarizes whether the trading system can continue controlled paper and Shadow runs.

## Constraints

- Do not trigger orders, observations, approvals, or lifecycle changes.
- Keep live and broker execution explicitly disabled.
- Aggregate existing subsystem facts instead of duplicating strategy logic.

## Implementation

- Add `trading_system_readiness` service.
- Expose `GET /api/mvp/strategy-lab/system-readiness`.
- Add Strategy Lab readiness panel for scheduler, lifecycle, ledger, Alpha, Shadow, and live-small gate state.

## Verification

- Unit tests for operational and blocked readiness states.
- Route test for system readiness endpoint.
- TypeScript build.
- Playwright Strategy Lab coverage.
