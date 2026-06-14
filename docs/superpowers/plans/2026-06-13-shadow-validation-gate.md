# Shadow Validation Gate

## Goal

Add a manual live-small precondition after Shadow observation. The gate should tell operators whether enough Shadow observations exist to consider a later live-small review, without promoting the strategy or creating broker orders.

## Constraints

- Do not auto-promote from paper or shadow to live-small.
- Do not create live, broker, or shadow orders.
- Use persisted `ShadowObservation` records as the evidence source.
- Keep AI and research workflows outside the execution path.

## Implementation

- Add `shadow_validation` service with a minimum Shadow observation sample gate.
- Expose `GET /api/mvp/strategy-lab/shadow-validation`.
- Add Strategy Lab Shadow validation panel.
- Refresh validation after manual Shadow observation recording.

## Verification

- Unit tests for collecting, validated, and blocked gate states.
- Route test for the Shadow validation endpoint.
- TypeScript build.
- Playwright Strategy Lab coverage on a non-reused port.
