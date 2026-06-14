# Shadow Review Packet

## Goal

Add a read-only review packet for the transition from paper validation to Shadow review.

## Constraints

- Do not auto-promote strategies.
- Do not modify lifecycle state.
- Do not create live or broker orders.
- Keep the packet based on persisted paper trading, event ledger, risk, and Alpha validation evidence.

## Implementation

- Add `shadow_review` service with strict Pydantic payloads.
- Compose evidence from Alpha gates, Alpha forecast, paper action plan, execution diagnostics, event ledger, and risk profile.
- Expose `GET /api/mvp/strategy-lab/shadow-review`.
- Add a Strategy Lab panel showing checklist, residual risks, recommended stage, and `auto_promotion_enabled=false`.

## Verification

- Unit tests for ready and blocked packets.
- Route test for the FastAPI endpoint.
- TypeScript build.
- Playwright test for Strategy Lab visibility.
- Docker API and browser runtime checks.
