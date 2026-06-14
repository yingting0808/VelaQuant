# Paper Event Ledger Repair

## Goal

Add a controlled repair path for historical paper runs that completed or skipped before runtime event persistence was available.

## Constraints

- Do not recalculate trades, fills, positions, or PnL.
- Do not repair running or failed runs.
- Persist only a truthful `run_audit` CoreEventLog entry for eligible runs with zero events.
- Keep the event-driven production path unchanged.

## Steps

1. Add paper operations repair payloads and service function.
2. Cover eligible repair and ineligible skip behavior with backend tests.
3. Expose a FastAPI route for repair.
4. Add a frontend repair action near the stability trend panel.
5. Verify with backend tests, frontend lint/build/E2E, Docker API, and browser.
