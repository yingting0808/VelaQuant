# Local Workspace Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local SQLite-backed workspace so portfolio positions, watchlist items, notes, and CSV imports are saved and reused by the app.

**Architecture:** Add a focused backend workspace service on top of existing SQLModel models and expose MVP routes from `mvp.py`. Replace static frontend module views for Portfolio, Watchlist, Notes, and Imports with client components that call typed helpers in `client-api.ts` and keep offline fallbacks.

**Tech Stack:** FastAPI, SQLModel, SQLite, pytest, Next.js App Router, React, TypeScript, Playwright.

---

## File Structure

- Create `apps/api/app/services/workspace.py`: local default workspace bootstrap, portfolio/watchlist/note CRUD, CSV import persistence.
- Create `apps/api/tests/test_workspace_service.py`: service-level tests.
- Modify `apps/api/app/api/routes/mvp.py`: workspace, portfolio, import, watchlist, note routes plus dashboard data source update.
- Modify `apps/api/tests/test_mvp_routes.py`: API coverage.
- Modify `apps/web/src/lib/client-api.ts`: workspace payload types and client helpers.
- Create `apps/web/src/components/portfolio-workspace.tsx`: editable portfolio table.
- Create `apps/web/src/components/watchlist-workspace.tsx`: editable watchlist.
- Create `apps/web/src/components/notes-workspace.tsx`: note creation/list.
- Create `apps/web/src/components/imports-workspace.tsx`: CSV import workflow.
- Modify `apps/web/src/app/portfolio/page.tsx`, `apps/web/src/app/watchlist/page.tsx`, `apps/web/src/app/notes/page.tsx`, `apps/web/src/app/imports/page.tsx`.
- Modify `apps/web/src/app/styles.css`: compact form/list styles.
- Modify `apps/web/tests/mvp.spec.ts`: browser flows for persistence workspaces.

---

### Task 1: Backend Workspace Service

**Files:**
- Create: `apps/api/app/services/workspace.py`
- Test: `apps/api/tests/test_workspace_service.py`

- [ ] **Step 1: Write failing service tests**

Create tests for default bootstrap, portfolio position upsert/delete, CSV import, watchlist upsert/delete, and note create/list.

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-local-workspace-persistence\apps\api
python -m pytest tests\test_workspace_service.py -v
```

Expected before implementation: FAIL because `app.services.workspace` does not exist.

- [ ] **Step 2: Implement workspace service**

Implement Pydantic payloads and functions:

```python
get_or_create_default_workspace(session)
get_workspace_summary(session)
get_portfolio_payload(session, provider)
upsert_position(session, data)
delete_position(session, ticker)
import_positions_csv(session, content)
list_watchlist_items(session)
upsert_watchlist_item(session, data)
delete_watchlist_item(session, ticker)
list_notes(session)
create_note(session, data)
```

- [ ] **Step 3: Rerun service tests**

Run:

```powershell
python -m pytest tests\test_workspace_service.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit service task**

```powershell
git add apps/api/app/services/workspace.py apps/api/tests/test_workspace_service.py
git commit -m "feat(api): add local workspace service"
```

---

### Task 2: Workspace API Routes

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write failing API tests**

Add tests for:

- `GET /api/mvp/workspace`
- `GET /api/mvp/portfolio`
- `PUT /api/mvp/portfolio/positions`
- `DELETE /api/mvp/portfolio/positions/{ticker}`
- `POST /api/mvp/portfolio/import`
- `GET/POST/DELETE /api/mvp/watchlist`
- `GET/POST /api/mvp/notes`
- dashboard portfolio reads workspace service

Run:

```powershell
python -m pytest tests\test_mvp_routes.py -v
```

Expected before implementation: FAIL on missing routes.

- [ ] **Step 2: Implement routes**

Use existing `get_session()` dependency and `get_market_data_provider()`. Map unknown delete targets to 404 and validation failures to 422.

- [ ] **Step 3: Rerun API tests**

```powershell
python -m pytest tests\test_mvp_routes.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit API task**

```powershell
git add apps/api/app/api/routes/mvp.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): expose local workspace routes"
```

---

### Task 3: Frontend API Helpers

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Add browser/client expectations**

Extend Playwright tests with mocked workspace endpoints for portfolio, watchlist, notes, and imports.

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-local-workspace-persistence\apps\web
npx playwright test --grep "portfolio workspace|watchlist workspace|notes workspace|imports workspace"
```

Expected before implementation: FAIL because UI and helpers are missing.

- [ ] **Step 2: Add typed client helpers**

Add payload types and helpers:

```ts
getPortfolio()
upsertPosition()
deletePosition()
importPositionsCsv()
getWatchlist()
upsertWatchlistItem()
deleteWatchlistItem()
getNotes()
createNote()
```

- [ ] **Step 3: Run TypeScript**

```powershell
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit client task**

```powershell
git add apps/web/src/lib/client-api.ts apps/web/tests/mvp.spec.ts
git commit -m "feat(web): add workspace api helpers"
```

---

### Task 4: Frontend Workspace Pages

**Files:**
- Create: `apps/web/src/components/portfolio-workspace.tsx`
- Create: `apps/web/src/components/watchlist-workspace.tsx`
- Create: `apps/web/src/components/notes-workspace.tsx`
- Create: `apps/web/src/components/imports-workspace.tsx`
- Modify: `apps/web/src/app/portfolio/page.tsx`
- Modify: `apps/web/src/app/watchlist/page.tsx`
- Modify: `apps/web/src/app/notes/page.tsx`
- Modify: `apps/web/src/app/imports/page.tsx`
- Modify: `apps/web/src/app/styles.css`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Implement client components**

Build compact data panels with form state, list rendering, save/delete/import actions, refresh after mutation, and visible fallback status.

- [ ] **Step 2: Wire pages**

Replace static `ModuleView` for portfolio, notes, imports, and add editable watchlist above `MarketSnapshotPanel`.

- [ ] **Step 3: Run focused frontend checks**

```powershell
npm run lint
npx playwright test --grep "portfolio workspace|watchlist workspace|notes workspace|imports workspace"
```

Expected: PASS.

- [ ] **Step 4: Commit UI task**

```powershell
git add apps/web/src/components/portfolio-workspace.tsx apps/web/src/components/watchlist-workspace.tsx apps/web/src/components/notes-workspace.tsx apps/web/src/components/imports-workspace.tsx apps/web/src/app/portfolio/page.tsx apps/web/src/app/watchlist/page.tsx apps/web/src/app/notes/page.tsx apps/web/src/app/imports/page.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "feat(web): add editable workspace pages"
```

---

### Task 5: Final Verification and Merge

**Files:**
- Modify only files touched above if failures expose defects.

- [ ] **Step 1: Backend verification**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-local-workspace-persistence\apps\api
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 2: Frontend verification**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-local-workspace-persistence\apps\web
npm run lint
npm run build
npx playwright test
```

Expected: PASS.

- [ ] **Step 3: Compose and browser verification**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-local-workspace-persistence
docker compose config
```

Then verify in browser that portfolio, watchlist, notes, and imports can save data.

- [ ] **Step 4: Merge locally**

Fast-forward merge back to `master`, rerun full verification on main, remove worktree, restart local services.

---

## Self-Review

- Spec coverage: backend workspace, API, frontend pages, imports, dashboard integration, and verification are covered.
- Scope control: no login, cloud sync, migration framework, rich text editor, or trading features.
- Type consistency: payload names are shared between route/service/client components.
- Test order: behavior tests are written before implementation.
- No open wording markers or ambiguous ownership.
