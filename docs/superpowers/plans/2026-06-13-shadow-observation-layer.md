# Shadow Observation Layer

## Goal

Add a non-execution Shadow observation layer after paper Alpha validation. The system should record what the strategy would have observed and routed, without creating broker orders or promoting lifecycle state.

## Constraints

- Do not auto-promote lifecycle stages.
- Do not create live, broker, or shadow orders.
- Keep observations idempotent per strategy and trading day.
- Persist observation records for audit and UI inspection.
- Require lifecycle `current_stage=shadow` before recording new Shadow observations.

## Implementation

- Add `ShadowObservation` SQLModel table.
- Add `shadow_observation` service with record and list functions.
- Expose:
  - `GET /api/mvp/strategy-lab/shadow-observations`
  - `POST /api/mvp/strategy-lab/shadow-observations/record`
- Add Strategy Lab Shadow observation panel and manual record action.
- Attach scheduled paper job to attempt one Shadow observation after the daily paper loop, skipping cleanly until lifecycle is in Shadow.

## Verification

- Unit tests for record, idempotency, and blocked observations.
- Unit tests for lifecycle-gated observation recording.
- Route tests for list and record endpoints.
- Scheduler tests for paper loop followed by Shadow observation, including lifecycle-gated skip.
- TypeScript build.
- Playwright Strategy Lab coverage.
- Docker API and browser runtime checks.
