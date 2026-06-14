# Live-small Review Packet

## Goal

Add a manual live-small review packet after Shadow validation. The packet should make the next gate visible while keeping automatic promotion and broker execution disabled.

## Constraints

- Do not promote lifecycle state automatically.
- Do not create live-small, live, broker, or shadow orders.
- Require the strategy to already be in `shadow` before live-small can be reviewed.
- Require Shadow validation to pass before live-small can be reviewed.
- Require Shadow observation health to be stable before live-small can be reviewed.

## Implementation

- Add `live_small_review` service with manual checklist and residual risk payloads.
- Expose `GET /api/mvp/strategy-lab/live-small-review`.
- Add Strategy Lab live-small review panel.
- Refresh live-small review state after Shadow observation and Shadow approval actions.
- Add `shadow_health_stable` as a live-small checklist gate.

## Verification

- Unit tests for paper-stage block, Shadow validation block, and ready-for-review state.
- Unit test for blocking live-small review when Shadow health is not stable.
- Route test for the live-small review endpoint.
- TypeScript build.
- Playwright Strategy Lab coverage on a non-reused port.
