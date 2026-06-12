# Paper Trading Daily Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local paper trading loop that generates candidates, explains them, simulates orders, records PnL, and creates daily review snapshots.

**Architecture:** Add SQLModel paper trading tables, a focused `paper_trading` service, `/api/mvp/paper-trading/*` routes, a `client-api.ts` client surface, and a `/paper-trading` workbench page. Keep all fills paper-only and synchronous, using the existing `MarketDataProvider` abstraction.

**Tech Stack:** FastAPI, SQLModel, Pydantic, pytest, Next.js 16, React 19, TypeScript, Playwright.

---

## File Structure

- Modify `apps/api/app/domain/models.py`: add paper account, candidate, order, position, and review tables.
- Create `apps/api/app/services/paper_trading.py`: own candidate generation, paper order simulation, mark-to-market, summary, and review calculations.
- Create `apps/api/tests/test_paper_trading_service.py`: focused service tests using in-memory SQLite and a fixture provider.
- Modify `apps/api/app/api/routes/mvp.py`: expose `/api/mvp/paper-trading/summary`, `/daily-run`, and `/orders`.
- Modify `apps/api/tests/test_mvp_routes.py`: route coverage for paper summary and daily run.
- Modify `apps/web/src/lib/client-api.ts`: add paper trading payload types and API functions.
- Create `apps/web/src/components/paper-trading-workspace.tsx`: render metrics, candidates, orders, positions, review, and actions.
- Create `apps/web/src/app/paper-trading/page.tsx`: page wrapper.
- Modify `apps/web/src/components/nav-panel.tsx`: add nav item.
- Modify `apps/web/tests/mvp.spec.ts`: E2E route and simulated buy coverage.

## Task 1: Backend Service Tests

**Files:**
- Create: `apps/api/tests/test_paper_trading_service.py`

- [ ] **Step 1: Write failing service tests**

Add tests for:

```python
def test_daily_run_creates_account_candidates_and_review():
    ...

def test_buy_order_fills_and_updates_cash_and_position():
    ...

def test_sell_order_realizes_profit_and_reduces_position():
    ...

def test_order_rejects_insufficient_cash_and_oversell():
    ...
```

Use an in-memory SQLModel session and a fixture provider returning AAPL at `100.0`, MSFT at `200.0`, and NVDA at `50.0`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_paper_trading_service.py -v
```

Expected: import failure because `app.services.paper_trading` does not exist.

## Task 2: Backend Models And Service

**Files:**
- Modify: `apps/api/app/domain/models.py`
- Create: `apps/api/app/services/paper_trading.py`

- [ ] **Step 1: Add models**

Add enum values for candidate/order/account/review state and SQLModel tables:

```python
class PaperTradingMode(str, Enum):
    paper = "paper"

class PaperCandidateStatus(str, Enum):
    proposed = "proposed"
    ordered = "ordered"
    dismissed = "dismissed"

class PaperOrderStatus(str, Enum):
    filled = "filled"
    rejected = "rejected"

class PaperOrderSide(str, Enum):
    buy = "buy"
    sell = "sell"

class PaperReadiness(str, Enum):
    collecting = "collecting"
    negative_expectancy = "negative_expectancy"
    watch = "watch"
    paper_ready = "paper_ready"
```

Then create `PaperAccount`, `PaperCandidate`, `PaperOrder`, `PaperPosition`, and `PaperReview`.

- [ ] **Step 2: Implement service**

Create Pydantic payloads and functions:

```python
def get_paper_trading_summary(session: Session, provider: MarketDataProvider) -> PaperTradingSummary: ...
def run_daily_paper_trading_loop(session: Session, provider: MarketDataProvider) -> PaperTradingSummary: ...
def submit_paper_order(session: Session, provider: MarketDataProvider, data: PaperOrderCreate) -> PaperOrderPayload: ...
```

The implementation must:

- create default account with `100000.0` cash;
- generate candidates from watchlist and portfolio tickers;
- fill market orders at provider quote price;
- reject insufficient cash and oversell with `ValueError`;
- calculate realized PnL on sells;
- mark positions to market;
- calculate review metrics and readiness.

- [ ] **Step 3: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_paper_trading_service.py -v
```

Expected: all service tests pass.

## Task 3: API Routes

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write failing route tests**

Add tests:

```python
def test_mvp_paper_trading_summary_route_returns_sections():
    ...

def test_mvp_paper_trading_daily_run_route_generates_candidates():
    ...
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_mvp_routes.py::test_mvp_paper_trading_summary_route_returns_sections tests/test_mvp_routes.py::test_mvp_paper_trading_daily_run_route_generates_candidates -v
```

Expected: `404 Not Found`.

- [ ] **Step 3: Add routes**

Expose:

```python
@router.get("/paper-trading/summary")
def paper_trading_summary(...)

@router.post("/paper-trading/daily-run")
def paper_trading_daily_run(...)

@router.post("/paper-trading/orders")
def paper_trading_order(...)
```

Translate `ValueError` into HTTP 400.

- [ ] **Step 4: Verify GREEN**

Run the route tests above, then:

```powershell
python -m pytest -q
```

Expected: full API test suite passes.

## Task 4: Web Client And UI

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Create: `apps/web/src/components/paper-trading-workspace.tsx`
- Create: `apps/web/src/app/paper-trading/page.tsx`
- Modify: `apps/web/src/components/nav-panel.tsx`

- [ ] **Step 1: Add client payloads and calls**

Add TypeScript types for account, candidate, order, position, review, summary, and order create input. Add:

```ts
export async function getPaperTradingSummary(): Promise<PaperTradingSummaryPayload>
export async function runPaperTradingDailyLoop(): Promise<PaperTradingSummaryPayload>
export async function submitPaperOrder(input: PaperOrderInputPayload): Promise<PaperOrderPayload | null>
```

- [ ] **Step 2: Add workspace UI**

Render metrics, candidate table, order table, position table, and review panel. Provide buttons:

- "运行今日模拟"
- "模拟买入 {ticker}"

Use Chinese copy, keep Ticker/PnL/API English terms unchanged.

- [ ] **Step 3: Add route and nav**

Add `/paper-trading` and the nav label `模拟盘`.

- [ ] **Step 4: Verify typecheck**

Run:

```powershell
npm run lint
```

Expected: TypeScript passes.

## Task 5: E2E

**Files:**
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Write E2E test**

Mock:

- `GET **/api/mvp/paper-trading/summary`
- `POST **/api/mvp/paper-trading/daily-run`
- `POST **/api/mvp/paper-trading/orders`

Test navigation to `/paper-trading`, daily run candidate rendering, and simulated buy success message.

- [ ] **Step 2: Verify**

Run:

```powershell
npx playwright test
```

Expected: all E2E tests pass.

## Task 6: Final Verification And Commit

**Files:**
- All touched files.

- [ ] **Step 1: Run backend tests**

```powershell
python -m pytest -q
```

- [ ] **Step 2: Run frontend checks**

```powershell
npm run lint
npm run build
npx playwright test
```

- [ ] **Step 3: Commit**

```powershell
git add apps docs
git commit -m "feat: add paper trading loop"
```

Expected: commit succeeds with a clean worktree afterward.
