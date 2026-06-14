# Manual Shadow Approval

## Goal

Add an explicit manual approval path from `paper` / `shadow_candidate` to `shadow` after the Shadow review packet is ready.

## Constraints

- No automatic promotion.
- No automatic kill.
- No live or broker execution.
- Approval must write an audit log.
- UI action must remain disabled when the Shadow review packet is blocked.

## Implementation

- Add `strategy_lifecycle_approval` service.
- Validate the Shadow review packet before changing lifecycle state.
- Persist manual stage change to `shadow` with `auto_transition_count=0`.
- Write `AuditLog(action="strategy_shadow_approved")`.
- Expose `POST /api/mvp/strategy-lab/lifecycle/approve-shadow`.
- Add a Strategy Lab manual approval button.

## Verification

- Unit tests for approval and blocked review rejection.
- Route test for the approval endpoint.
- TypeScript build.
- Playwright coverage for disabled approval when review is blocked.
