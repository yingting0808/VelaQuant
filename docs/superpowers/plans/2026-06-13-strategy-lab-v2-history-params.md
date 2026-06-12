# Strategy Lab V2 History Params Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable LEAN project parameters and local backtest history to Strategy Lab.

**Architecture:** Keep strategy parameter definitions in the existing catalog, validate and normalize them in backend services, and execute LEAN from per-run runtime workspace copies so repository config files are never mutated by a run. Persist latest plus a bounded JSON history index in `apps/api/.runtime/strategy-lab`, and expose the history through FastAPI for a compact Next.js research UI.

**Tech Stack:** FastAPI, Pydantic, pytest, QuantConnect LEAN project parameters, subprocess, Next.js App Router, React, TypeScript, Playwright.

---

## Execution Notes

- Worktree: `D:\Documents\AI美股\.worktrees\codex-strategy-lab-v2`
- Branch: `codex/strategy-lab-v2-history-params`
- Design spec: `docs/superpowers/specs/2026-06-13-strategy-lab-v2-history-params-design.md`
- Use TDD for behavior changes: add or update failing tests first, run the focused tests to observe failure, implement, rerun.
- Automated tests must not call real Docker, real LEAN CLI, or external network.
- Do not add live trading, broker connections, cloud backtests, user code upload, AI executable strategy generation, or system dependency installers.
- QuantConnect docs confirm project parameters belong in `config.json` under `parameters` and are read from algorithms with `get_parameter` / `GetParameter`.

## File Structure

- Modify `apps/api/lean-workspace/strategies.json`: add strategy parameter definitions.
- Modify `apps/api/lean-workspace/MovingAverageCross/config.json`: add default string parameters.
- Modify `apps/api/lean-workspace/MovingAverageCross/main.py`: read LEAN project parameters.
- Modify `apps/api/app/services/strategy_catalog.py`: define public parameter metadata.
- Modify `apps/api/app/services/lean_backtest.py`: validate parameters, prepare runtime workspace, write per-run config, save/read history.
- Modify `apps/api/app/api/routes/mvp.py`: accept parameterized requests and expose history.
- Modify `apps/api/tests/test_strategy_catalog.py`: catalog parameter assertions.
- Modify `apps/api/tests/test_lean_backtest_service.py`: service tests for validation, workspace copy, history.
- Modify `apps/api/tests/test_mvp_routes.py`: API tests for parameter requests and history.
- Modify `apps/web/src/lib/client-api.ts`: payload types and helpers for parameters/history.
- Modify `apps/web/src/components/strategy-backtest-panel.tsx`: parameter controls, history list, action hints.
- Modify `apps/web/src/app/styles.css`: compact controls and history styles.
- Modify `apps/web/tests/mvp.spec.ts`: Playwright coverage for parameter request and history display.

---

### Task 1: Catalog Parameters and LEAN Algorithm Defaults

**Files:**
- Modify: `apps/api/lean-workspace/strategies.json`
- Modify: `apps/api/lean-workspace/MovingAverageCross/config.json`
- Modify: `apps/api/lean-workspace/MovingAverageCross/main.py`
- Modify: `apps/api/app/services/strategy_catalog.py`
- Test: `apps/api/tests/test_strategy_catalog.py`

- [ ] **Step 1: Extend catalog tests first**

Add assertions that the checked-in `moving_average_cross` strategy exposes public parameter definitions for `symbol`, `start_date`, `end_date`, `cash`, `fast_period`, and `slow_period`, and that `public_payload()` includes `parameters` but omits `project_path`.

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-strategy-lab-v2\apps\api
python -m pytest tests\test_strategy_catalog.py -v
```

Expected before implementation: FAIL because `StrategyDefinition` has no `parameters` field.

- [ ] **Step 2: Add catalog parameter schema and metadata**

Implement `StrategyParameterDefinition` in `strategy_catalog.py` with fields `name`, `label`, `kind`, `default`, `min`, `max`, and `required`. Add `parameters` to `StrategyDefinition`, include it in `public_payload()`, and keep path validation unchanged.

Update `strategies.json` with the six defaults from the design.

- [ ] **Step 3: Parameterize the LEAN sample**

Update `MovingAverageCross/config.json` with string `parameters`.

Update `main.py` so `Initialize` reads:

```python
symbol_value = str(self.GetParameter("symbol", "AAPL")).upper()
start_date = str(self.GetParameter("start_date", "2020-01-01"))
end_date = str(self.GetParameter("end_date", "2021-01-01"))
cash = float(self.GetParameter("cash", 100000))
fast_period = int(self.GetParameter("fast_period", 20))
slow_period = int(self.GetParameter("slow_period", 50))
```

Parse dates with `datetime.strptime(value, "%Y-%m-%d")` and pass parsed year/month/day to `SetStartDate` and `SetEndDate`.

- [ ] **Step 4: Rerun catalog tests**

Run:

```powershell
python -m pytest tests\test_strategy_catalog.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit task**

Commit:

```powershell
git add apps/api/lean-workspace/strategies.json apps/api/lean-workspace/MovingAverageCross/config.json apps/api/lean-workspace/MovingAverageCross/main.py apps/api/app/services/strategy_catalog.py apps/api/tests/test_strategy_catalog.py
git commit -m "feat(api): add strategy parameter metadata"
```

---

### Task 2: Parameter Validation, Runtime Workspace, and History

**Files:**
- Modify: `apps/api/app/services/lean_backtest.py`
- Test: `apps/api/tests/test_lean_backtest_service.py`

- [ ] **Step 1: Add failing service tests**

Add tests for:

- default parameters are attached to every `BacktestResult`.
- caller parameters override defaults and are written to runtime project `config.json`.
- command cwd is the per-run runtime workspace.
- invalid ticker raises `ValueError`.
- start date after end date raises `ValueError`.
- fast period greater than or equal to slow period raises `ValueError`.
- unready runs do not create a runtime workspace but still write latest/history.
- success and failed results are both included in history newest first.
- corrupt history JSON returns an empty list.

Run:

```powershell
python -m pytest tests\test_lean_backtest_service.py -v
```

Expected before implementation: FAIL on missing parameter/history APIs.

- [ ] **Step 2: Implement request normalization**

Add `BacktestParameters = dict[str, str]`, defaults extracted from catalog definitions, and validation helpers:

- `_normalize_backtest_parameters(strategy, overrides)`
- `_normalize_ticker`
- `_parse_date`
- `_parse_int`
- `_parse_number`

Raise `ValueError` with readable messages for validation failures. Preserve `UnknownStrategyError` behavior from the catalog.

- [ ] **Step 3: Implement runtime workspace preparation**

Copy only the selected strategy project to:

```text
<runtime_root>/workspaces/<run_id>/<project_name>
```

Write merged parameters into that copy's `config.json`. Keep the checked-in `lean-workspace` untouched.

Change the command cwd to `<runtime_root>/workspaces/<run_id>` and command to:

```python
["lean", "backtest", strategy.project_path.name, "--output", str(output_dir)]
```

- [ ] **Step 4: Extend result and history models**

Add `parameters` to `BacktestResult`.

Add `BacktestHistoryItem` and these functions:

- `_history_path(runtime_root)`
- `_save_history_item(result, runtime_root, limit=50)`
- `read_backtest_history(runtime_root=DEFAULT_RUNTIME_ROOT, limit=10)`

Update all code paths that create an empty result or parsed success result so latest and history are both saved.

- [ ] **Step 5: Rerun service tests**

Run:

```powershell
python -m pytest tests\test_lean_backtest_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit task**

Commit:

```powershell
git add apps/api/app/services/lean_backtest.py apps/api/tests/test_lean_backtest_service.py
git commit -m "feat(api): add parameterized backtest history"
```

---

### Task 3: API Routes

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Add failing API tests**

Extend API tests so:

- `POST /api/mvp/strategy-lab/backtests` accepts a `parameters` map and passes it to `run_lean_backtest`.
- invalid parameter errors become 422.
- `GET /api/mvp/strategy-lab/backtests/history` returns `{"history": [...]}`.
- strategy payload contains `parameters`.

Run:

```powershell
python -m pytest tests\test_mvp_routes.py -v
```

Expected before implementation: FAIL because route signatures and history endpoint are missing.

- [ ] **Step 2: Implement route changes**

Update `BacktestBody`:

```python
class BacktestBody(BaseModel):
    strategy_id: str = Field(min_length=1)
    parameters: dict[str, str] = Field(default_factory=dict)
```

Call:

```python
result = run_lean_backtest(body.strategy_id, parameter_overrides=body.parameters)
```

Catch `ValueError` for validation failures and raise `HTTPException(status_code=422, detail=str(error))`, while keeping `UnknownStrategyError` mapped to 404.

Add:

```python
@router.get("/strategy-lab/backtests/history")
def strategy_lab_backtest_history(limit: int = 10) -> dict:
    return {"history": [item.model_dump() for item in read_backtest_history(limit=limit)]}
```

- [ ] **Step 3: Rerun API tests**

Run:

```powershell
python -m pytest tests\test_mvp_routes.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit task**

Commit:

```powershell
git add apps/api/app/api/routes/mvp.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): expose backtest history"
```

---

### Task 4: Frontend Parameter Form and History

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/strategy-backtest-panel.tsx`
- Modify: `apps/web/src/app/styles.css`
- Test: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Update Playwright tests first**

Extend Strategy Lab tests so the mocked strategy includes parameter definitions, the UI shows default inputs, the POST body includes `parameters`, and a mocked history response appears in the history list.

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-strategy-lab-v2\apps\web
npx playwright test --grep "strategy lab can run a cataloged LEAN backtest"
```

Expected before implementation: FAIL because the UI has no parameter inputs/history helper.

- [ ] **Step 2: Extend client API types**

Add parameter definition and history payload types, validate them in existing guard style, update `runStrategyBacktest(strategyId, parameters)` to include parameters, and add `getBacktestHistory(limit = 10)`.

Keep fallbacks valid when the backend is offline.

- [ ] **Step 3: Add form state and history loading**

In `StrategyBacktestPanel`:

- Initialize form state from selected strategy parameters.
- Reset form defaults when selected strategy changes.
- Submit `runStrategyBacktest(selectedStrategy.id, parameterValues)`.
- Load history on mount.
- Refresh history after each run.
- Render a compact history list below metrics.
- Render unready action hints when result status is `unavailable`.

- [ ] **Step 4: Add styles**

Add responsive styles for:

- `.parameter-form`
- `.parameter-grid`
- `.parameter-field`
- `.history-list`
- `.history-item`
- `.action-hints`

Keep controls compact and consistent with the current tool UI.

- [ ] **Step 5: Rerun frontend focused checks**

Run:

```powershell
npm run lint
npx playwright test --grep "strategy lab can run a cataloged LEAN backtest|strategy lab displays LEAN backtest failures"
```

Expected: PASS.

- [ ] **Step 6: Commit task**

Commit:

```powershell
git add apps/web/src/lib/client-api.ts apps/web/src/components/strategy-backtest-panel.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "feat(web): add strategy parameters and history"
```

---

### Task 5: Final Verification and Browser QA

**Files:**
- Modify only files touched by earlier tasks if verification exposes a failure.

- [ ] **Step 1: Run backend full suite**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-strategy-lab-v2\apps\api
python -m pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 2: Run frontend lint/build/E2E**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-strategy-lab-v2\apps\web
npm install
npm run lint
npm run build
npx playwright test
```

Expected: all frontend checks PASS.

- [ ] **Step 3: Validate Compose**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-strategy-lab-v2
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if (Test-Path $dockerBin) { $env:Path = "$dockerBin;$env:Path" }
docker compose config
```

Expected: command exits successfully. If Docker CLI is unavailable, record the exact error and confirm app still handles unavailable status.

- [ ] **Step 4: Browser verification**

Start the API and web app from the worktree, then use the in-app browser:

- `/strategy-lab` renders readiness plus LEAN 回测.
- Parameter defaults are visible.
- Clicking `运行回测` shows structured success, failed, or unavailable result.
- History section renders.
- `/watchlist`, `/settings`, and dashboard still render.

- [ ] **Step 5: Commit verification fixes**

If any code changes during verification:

```powershell
git add apps/api apps/web docs
git commit -m "fix: stabilize strategy lab v2"
```

If no code changed:

```powershell
git status --short
```

Expected: clean working tree.

---

## Self-Review

- Spec coverage: parameter metadata, runtime workspace, LEAN config parameters, latest/history persistence, API routes, frontend form/history, and verification are covered.
- Scope control: no live trading, brokers, cloud backtests, custom code execution, automatic system installs, or optimization grid.
- Type consistency: backend result `parameters` and history payloads have matching frontend types.
- Test order: tasks require failing tests before implementation and focused reruns after implementation.
- No open wording markers or ambiguous file ownership.
