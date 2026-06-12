# Paper Trading Daily Loop Design

## Objective

Build a local-first paper trading loop for VelaQuant that can run every trading day and produce an auditable research-to-simulation workflow:

1. generate ranked candidates from the current watchlist and portfolio context;
2. explain the thesis, risks, evidence, and sizing rationale for each candidate;
3. simulate orders and fills without any live broker integration;
4. mark paper positions to market and record realized/unrealized PnL;
5. summarize strategy review metrics such as win rate, average win/loss, expectancy, and readiness for small live trading.

This stage intentionally does not place real orders. The system must make the paper/live boundary explicit and keep the default mode in paper trading.

## Scope

This implementation covers a single local workspace and one default paper account. It uses existing provider abstractions for prices and evidence, SQLModel for persistence, and the current `/api/mvp` route style. The UI adds a paper trading workbench rather than changing the existing dashboard flow.

Out of scope for this stage:

- broker APIs;
- live order routing;
- margin, options, shorts, borrowing, corporate actions, and tax lots;
- intraday scheduling automation;
- predictive ML model training;
- capital allocation across multiple accounts.

## Architecture

The feature adds a paper trading service module behind FastAPI routes. The service reads the default workspace, creates candidate records, creates simulated orders, applies deterministic fills at provider quote prices, updates paper positions, and records review snapshots.

The UI consumes these routes through `client-api.ts` and renders a new "模拟盘" page inside the existing `AppShell`. Existing data providers stay behind `MarketDataProvider`; if OpenBB or SEC is unavailable, the current mock fallback keeps the loop testable.

## Data Model

New SQLModel tables:

- `PaperAccount`: one local paper account with starting cash, current cash, mode, and creation time.
- `PaperCandidate`: candidate ticker, action, rank, confidence, thesis, risk notes, evidence summary, proposed quantity, and status.
- `PaperOrder`: simulated buy/sell order, quantity, limit/market type, status, fill price, submitted time, and filled time.
- `PaperPosition`: current simulated quantity, average cost, last price, market value, unrealized PnL, realized PnL, and update time.
- `PaperReview`: daily review snapshot with equity, cash, realized/unrealized PnL, win rate, average win/loss, expectancy, and readiness state.

The MVP uses long-only buy/sell actions. Sell orders cannot create negative positions.

## Candidate Generation

The first version uses a conservative deterministic engine:

- Seed source: current watchlist tickers plus existing portfolio tickers.
- Quote source: `MarketDataProvider.get_quote`.
- Evidence source: `MarketDataProvider.get_research_evidence`.
- Ranking: evidence count, quote availability, portfolio exposure, and simple diversification preference.
- Output: top candidates with action `buy`, default proposed quantity sized by a small notional cap.

This keeps the feature stable and testable. The candidate generator boundary is deliberately narrow so a richer scoring model can replace it without changing API consumers.

## Paper Order Simulation

Orders are simulated synchronously for this MVP:

- `POST /api/mvp/paper-trading/orders` creates an order.
- Market orders fill immediately at the latest quote price.
- Buy orders require sufficient paper cash.
- Sell orders require sufficient paper quantity.
- Every fill updates cash, paper position, realized PnL, and unrealized PnL.

This is intentionally simple so the first loop can run every day without needing a queue, broker adapter, or background worker.

## Review And Readiness

`POST /api/mvp/paper-trading/daily-run` performs the daily loop:

1. ensure the paper account exists;
2. generate candidates;
3. mark existing paper positions to market;
4. write a review snapshot.

The review exposes a readiness state:

- `collecting`: fewer than 20 closed paper trades;
- `negative_expectancy`: expectancy is below or equal to zero;
- `watch`: positive expectancy but fewer than 30 closed trades or drawdown too high;
- `paper_ready`: positive expectancy with enough closed trades and acceptable drawdown.

The UI must phrase this as research readiness, not investment advice.

## API Surface

New routes under `/api/mvp/paper-trading`:

- `GET /summary`: account, candidates, orders, positions, latest review, and readiness.
- `POST /daily-run`: generate candidates, mark positions, and record review.
- `POST /orders`: create and simulate one order.

The API response should be complete enough for one page to render without chaining many requests.

## UI

Add `/paper-trading` with:

- top metrics: paper equity, cash, realized PnL, unrealized PnL, expectancy, readiness;
- primary action: run daily simulation;
- candidate table with ticker, action, confidence, proposed quantity, reason, risk, and a "模拟买入" action;
- paper orders table;
- paper positions table;
- review panel with latest daily notes.

The nav adds "模拟盘". The page uses existing compact operations-console styling and Chinese labels. Tickers, SEC, OpenBB, LEAN, PnL, API, and English strategy identifiers are not translated.

## Error Handling

- Missing quote price prevents candidate order fill and returns a 400-level API error.
- Insufficient cash prevents buy fills.
- Insufficient quantity prevents sell fills.
- Candidate generation continues if one ticker has unavailable evidence or quote data.
- The loop remains usable in mock-data mode.

## Tests

Backend tests cover:

- daily run creates an account, candidates, and review;
- buy order fills and updates cash/position;
- sell order realizes PnL;
- oversell and insufficient cash are rejected;
- summary route returns all major sections.

Frontend/E2E tests cover:

- nav reaches the paper trading page;
- daily run renders candidates and review metrics;
- a simulated buy updates orders/positions in the UI.

## Default Decisions

The implementation uses the recommended conservative default:

- paper-only;
- long-only;
- synchronous simulated fills;
- one default local paper account;
- deterministic candidate scoring;
- no live broker code;
- no background scheduler until the manual daily loop is proven.
