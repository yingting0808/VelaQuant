# Shadow Observation Health

## Goal

Add a read-only Shadow observation health layer so Shadow samples are evaluated for quality, not only counted.

## Constraints

- Do not create orders or lifecycle transitions.
- Use persisted `ShadowObservation` rows as evidence.
- Keep live and broker execution disabled.

## Implementation

- Add `shadow_observation_health` service.
- Expose `GET /api/mvp/strategy-lab/shadow-observation-health`.
- Add Strategy Lab Shadow health panel.
- Track sample readiness, consecutive observations, average would-route count, event chain count, residual risk count, and warnings.

## Verification

- Unit tests for collecting, stable, and blocked health states.
- Route test for health endpoint.
- TypeScript build.
- Playwright Strategy Lab coverage.
