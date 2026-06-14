# Alpha Validation Forecast

## Goal

Add a read-only forecast layer that estimates how many additional paper sessions are needed for the current strategy to satisfy the existing Alpha validation gates.

## Constraints

- Do not change risk limits.
- Do not promote, demote, kill, or mutate any strategy.
- Do not let AI generate trade intent or influence execution.
- Use existing FastAPI, Pydantic, SQLModel service patterns.
- Keep the forecast derived from already persisted paper validation data.

## Implementation

- Add `alpha_validation_forecast` service with strict Pydantic payloads.
- Estimate sample-count gates from current per-review-day rates.
- Mark expectancy and drawdown quality gates as unforecastable when they are blockers.
- Expose `GET /api/mvp/strategy-lab/alpha-forecast`.
- Add a paper trading workspace panel for the forecast.
- Cover service, route, build, and E2E behavior.

## Verification

- Unit tests for ready, forecastable, and blocked forecast states.
- Route test for the API payload.
- Web build for TypeScript and production rendering.
- Playwright coverage for the new panel.
- Docker API and in-app browser checks against real runtime data.
