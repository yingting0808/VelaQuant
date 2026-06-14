# Lifecycle Audit View

## Goal

Expose lifecycle approval audit records in the Strategy Lab so manual Shadow approvals are visible and reviewable after they happen.

## Constraints

- Read audit logs only; do not mutate lifecycle state from the audit view.
- Preserve automatic promotion as disabled.
- Show manual approval metadata from persisted `AuditLog` rows.

## Implementation

- Add `strategy_lifecycle_audit` service.
- Expose `GET /api/mvp/strategy-lab/lifecycle/audit`.
- Add Strategy Lab lifecycle audit panel.

## Verification

- Unit tests for populated and empty lifecycle audit history.
- Route test for lifecycle audit endpoint.
- TypeScript build.
- Playwright Strategy Lab coverage.
