# VelaQuant — Self-Owned Trading Core for US Equities

> **30-second answer: VelaQuant has its own Trading Core.** The runtime order path is implemented by VelaQuant in `apps/api/app/trading_core/`; LEAN/vectorbt, OpenBB, LangGraph, and AI models are surrounding research, data, backtest, and explanation tools only.
>
> **30 秒结论：VelaQuant 有自己的 Trading Core。** 运行时订单链路由 VelaQuant 自研实现于 `apps/api/app/trading_core/`；LEAN/vectorbt、OpenBB、LangGraph 和 AI 模型只是外围的研究、数据、回测和解释工具，不替代 Trading Core。

## Manuals / 手册

- User manual: [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md)
- Operations and architecture guide: [`docs/SYSTEM_OPERATIONS_GUIDE.md`](docs/SYSTEM_OPERATIONS_GUIDE.md)

中文入口：

- 用户手册：[`docs/USER_MANUAL.md`](docs/USER_MANUAL.md)
- 系统操作与架构说明：[`docs/SYSTEM_OPERATIONS_GUIDE.md`](docs/SYSTEM_OPERATIONS_GUIDE.md)

The user manual explains Web UI pages, daily workflow, what each function helps users achieve, AI assistant capabilities, professional terms, implementation logic, and features still under development. The operations guide keeps the deeper runtime, Trading Core, Docker, API, and audit-oriented details.

用户手册按 Web UI 功能写，说明每天做什么、能达到什么效果、每项功能怎么用、背后怎么运行，以及哪些能力还在研发中；系统操作与架构说明保留更深入的 Trading Core、Docker、API 和审计视角内容。

## GitHub Quick Proof / GitHub 首屏证据

**VelaQuant has its own event-driven Trading Core. It is not a LEAN, OpenBB, LangGraph, vectorbt, or frontend wrapper.**

**VelaQuant 有自己的事件驱动 Trading Core，不是 LEAN、OpenBB、LangGraph、vectorbt 或前端页面的套壳。**

The quickest proof is the runtime code path, not a marketing label:

最快证据是运行时代码路径，不是宣传标签：

| Question | Answer |
| --- | --- |
| Does VelaQuant own its Trading Core? | **Yes.** See `apps/api/app/trading_core/`. |
| What owns paper/live-small execution flow? | VelaQuant `TradingEngine -> RiskEngine -> ExecutionEngine -> EventLedger`. |
| Does LEAN or vectorbt replace the runtime? | **No.** They are research/backtest tools only. |
| Does OpenBB execute trades? | **No.** OpenBB is data/research access only. |
| Does LangGraph or AI generate executable orders? | **No.** LangGraph orchestrates research workflow; optional OpenAI-compatible LLM integration is research/explanation only. |

| 问题 | 回答 |
| --- | --- |
| VelaQuant 是否有自研 Trading Core？ | **有。** 代码在 `apps/api/app/trading_core/`。 |
| 模拟盘 / live-small 执行主路径由谁负责？ | VelaQuant `TradingEngine -> RiskEngine -> ExecutionEngine -> EventLedger`。 |
| LEAN 或 vectorbt 是否替代交易运行时？ | **不是。** 它们只用于研究 / 回测。 |
| OpenBB 是否负责下单？ | **不是。** OpenBB 只用于数据 / 研究访问。 |
| LangGraph 或 AI 是否生成可执行订单？ | **不是。** LangGraph 编排投研 workflow；可选 OpenAI-compatible LLM 集成只做投研解释。 |

Repository proof path for the owned Trading Core:

自研 Trading Core 的仓库证据路径：

```text
apps/api/app/trading_core/
  engine.py           TradingEngine orchestration
  strategy_engine.py  Strategy boundary
  risk.py             Risk gatekeeper
  execution.py        Order state machine
  event_bus.py        EventEnvelope + Redis stream bus
  portfolio.py        Portfolio state

apps/api/app/services/strategy_runtime.py
apps/api/app/services/paper_trading.py
```

Runtime proof path:

运行态证据路径：

```text
StrategyRegistry
  -> StrategyExecutionBinding
  -> TradingEngine
  -> EventBus
  -> StrategyEngine
  -> RiskEngine
  -> ExecutionEngine
  -> EventLedger
```

Code proof:

代码证据：

- Trading Core implementation: `apps/api/app/trading_core/`
- Runtime strategy binding: `apps/api/app/services/strategy_runtime.py`
- Paper execution integration: `apps/api/app/services/paper_trading.py`
- Core tests: `apps/api/tests/test_trading_core.py`, `apps/api/tests/test_strategy_runtime.py`, `apps/api/tests/test_strategy_control.py`

中文对应：

- Trading Core 实现：`apps/api/app/trading_core/`
- 运行时策略绑定：`apps/api/app/services/strategy_runtime.py`
- 模拟盘执行接入：`apps/api/app/services/paper_trading.py`
- 内核测试：`apps/api/tests/test_trading_core.py`、`apps/api/tests/test_strategy_runtime.py`、`apps/api/tests/test_strategy_control.py`

External frameworks are support tools around the core, not replacements for it:

外部框架只是 Trading Core 周边支撑工具，不替代 Trading Core：

| Tool | Role | Not Allowed To Do |
| --- | --- | --- |
| LEAN / vectorbt | Research and backtesting | Replace live/paper execution runtime |
| OpenBB | Data and research access | Act as broker, risk engine, or execution adapter |
| LangGraph | AI research workflow orchestration | Generate executable `TradeIntent` or call execution |
| OpenAI-compatible LLM | Optional research explanation LLM through Responses or Chat Completions | Generate executable orders, risk decisions, or execution calls |

| 工具 | 职责 | 明确禁止 |
| --- | --- | --- |
| LEAN / vectorbt | 研究与回测 | 替代模拟盘/实盘执行运行时 |
| OpenBB | 数据与研究访问 | 充当券商、风控或执行适配器 |
| LangGraph | AI 投研 workflow 编排 | 生成可执行 `TradeIntent` 或调用执行链 |
| OpenAI-compatible LLM | 通过 Responses 或 Chat Completions 接入的可选投研解释 LLM | 生成可执行订单、风控决策或执行调用 |

VelaQuant is a local-first US equities research and paper-trading system built around that owned Trading Core for building a verifiable alpha loop before any small-capital live deployment.

VelaQuant 是一个以上述自研 Trading Core 为中心的本地优先美股投研与模拟交易系统，目标是在进入小资金实盘前，先建立可验证的 Alpha 闭环。

This project is not a simple trading bot and not a wrapper around LEAN, OpenBB, or LangGraph. It is an event-driven trading-system foundation that separates market data, strategy decisions, risk control, execution, paper accounting, backtesting, and AI-assisted research.

本项目不是简单的交易机器人，也不是 LEAN、OpenBB 或 LangGraph 的套壳。它是事件驱动的交易系统底座，将市场数据、策略决策、风控、执行、模拟盘记账、回测和 AI 辅助研究拆分为清晰边界。

## Core Ownership / 核心归属

**Trading Core is owned by VelaQuant.** The code lives in `apps/api/app/trading_core/` and includes the runtime components that turn strategy output into audited paper-trading state:

**Trading Core 是 VelaQuant 自研拥有的核心。** 代码位于 `apps/api/app/trading_core/`，包含把策略输出转成可审计模拟交易状态的运行时组件：

```text
apps/api/app/trading_core/
  engine.py           TradingEngine orchestration
  event_bus.py        EventEnvelope, event topics, Redis stream event bus
  strategy_engine.py  StrategyEngine and strategy binding boundary
  risk.py             RiskEngine and RiskLimits
  execution.py        ExecutionEngine and order state machine
  portfolio.py        PortfolioState and positions
```

External tools are deliberately kept outside the production execution path:

外部工具被明确隔离在生产执行路径之外：

- **LEAN / vectorbt**: research and backtest only.
- **OpenBB**: data and research access only.
- **LangGraph**: AI research workflow orchestration only.
- **AI models**: explanation and research only; they do not generate executable `TradeIntent`.

中文边界：

- **LEAN / vectorbt**：只用于研究和回测。
- **OpenBB**：只用于数据和研究访问。
- **LangGraph**：只用于 AI 投研 workflow 编排。
- **AI 模型**：只做解释和研究，不生成可执行 `TradeIntent`。

## Read This First / 先读这一段

VelaQuant has its own Trading Core. The core is implemented in `apps/api/app/trading_core/` and owns the runtime path from strategy binding to risk approval, execution state transitions, and event-ledger persistence.

VelaQuant 有自己的自研 Trading Core。核心代码位于 `apps/api/app/trading_core/`，负责从策略绑定、风控审批、执行状态机到事件账本落库的运行主路径。

External frameworks do not replace the Trading Core:

外部框架不会替代 Trading Core：

| Area | VelaQuant-owned core | External tools |
| --- | --- | --- |
| Trading runtime | `TradingEngine`, `StrategyEngine`, `RiskEngine`, `ExecutionEngine`, `EventLedger` | Not LEAN, not OpenBB, not LangGraph |
| Backtest and research | Strategy Lab and core-compatible strategy contracts | LEAN/vectorbt are research/backtest tools only |
| Data and AI | Data-provider abstraction and AI research workflow boundary | OpenBB is data/research access; LangGraph orchestrates research workflows |

中文对应：

| 领域 | VelaQuant 自研核心 | 外部工具定位 |
| --- | --- | --- |
| 交易运行时 | `TradingEngine`、`StrategyEngine`、`RiskEngine`、`ExecutionEngine`、`EventLedger` | 不是 LEAN、不是 OpenBB、不是 LangGraph |
| 回测与研究 | 策略实验室和兼容 Trading Core 的策略契约 | LEAN/vectorbt 只用于研究和回测 |
| 数据与 AI | 数据源抽象层和 AI 投研 workflow 边界 | OpenBB 是数据/研究访问；LangGraph 编排投研 workflow |

## Current System Role / 当前系统定位

VelaQuant currently focuses on controlled paper trading:

VelaQuant 当前重点是受控模拟交易：

- Generate daily strategy candidates from Registry-controlled paper runtime strategies, currently `deterministic_watchlist_v1` and `moving_average_cross`.
- Explain candidate rationale with structured evidence.
- Route simulated orders through the Trading Core risk and execution chain.
- Persist event-ledger traces for audit and replay.
- Record paper PnL, reviews, and strategy diagnostics.
- Run historical research backtests through the Strategy Lab.
- Keep AI out of the production execution path.

中文对应能力：

- 从 Strategy Registry 控制的 paper runtime 策略生成每日候选，目前包括 `deterministic_watchlist_v1` 和 `moving_average_cross`。
- 用结构化证据解释候选原因。
- 将模拟订单统一送入 Trading Core 的风控与执行链路。
- 持久化事件账本，支持审计和回放。
- 记录模拟盘盈亏、复盘和策略诊断。
- 通过策略实验室运行历史回测。
- 保持 AI 与生产执行路径隔离。

The system is designed to prove paper-trading expectancy and execution discipline before moving toward live-small trading.

系统设计目标是在进入 live-small 前，先证明模拟盘净期望、执行纪律和风控链路稳定。

## Current Verified Progress / 当前已验证进度

Runtime-verified on Docker Compose as of 2026-06-15:

截至 2026-06-15，已在 Docker Compose 运行态验证：

- API, web, PostgreSQL, and Redis run together through Docker Compose.
- `GET /api/mvp/data-sources/status` returns `provider_mode=hybrid` with Mock, SEC EDGAR, and OpenBB available in the current Docker runtime.
- `GET /api/mvp/ai/status` returns LangGraph research workflow availability and OpenAI-compatible research-LLM status. In the current Docker runtime checked on 2026-06-15, the research LLM is configured and available (`configured=true`, `available=true`, model `mimo-v2.5-pro`); `ai_generates_trade_intent`, `ai_influences_risk`, and `ai_calls_execution` are all `false`.
- `GET/PUT /api/mvp/runtime-settings` backs the Web Settings page, where runtime operators can adjust data mode, SEC EDGAR User-Agent, LEAN backtest timeout, OpenAI Research LLM model/base URL/timeout, and save or clear an OpenAI API key. Stored API keys are used by the backend but are never returned in API responses; scheduler startup and Redis wiring still come from environment variables.
- `GET /api/mvp/strategy-lab/status` now reports Docker CLI, Docker Compose, Docker engine, LEAN CLI, cached `quantconnect/lean:latest`, and vectorbt readiness. The current Docker runtime has the QuantConnect LEAN engine image cached locally.
- `POST /api/mvp/strategy-lab/backtests` is runtime-verified on the LEAN engine with OpenBB/yfinance real historical bars injected as LEAN `PythonData` custom data. Latest verified LEAN run `20260615T051211211740Z-moving_average_cross` returned `data_source=openbb_yfinance`, `data_quality=real_market_data`, `uses_real_market_data=true`, `total_net_profit=71.330%`, `sharpe_ratio=2.114`, `drawdown=20.300%`, and `total_trades=3`.
- `deterministic_watchlist_v1` still uses vectorbt for active-strategy historical replay; latest verified vectorbt/OpenBB run `20260615T050310967734Z-deterministic_watchlist_v1` returned `data_quality=real_market_data`, `total_net_profit=38.60%`, `sharpe_ratio=1.45`, `drawdown=17.91%`, and `total_trades=8`. vectorbt remains research/backtest only and does not replace the runtime Trading Core.
- `POST /api/mvp/research` returns `status=complete_llm` only when the OpenAI-compatible LLM call succeeds; without a key or after provider failure, the same endpoint returns deterministic LangGraph research output and preserves `requires_human_review=true`. The Web AI sidecar now displays either `LLM 可用` or `本地规则`, and local-rule results are labeled `本地规则` instead of looking like an LLM response.
- The Web AI sidecar can collapse into a compact AI rail and expand back without disabling research actions; expanded prompts still call the real `/api/mvp/research` path and can save research output as notes.
- `POST /api/mvp/paper-trading/action-plan/execute-primary` executes quick safe actions synchronously and queues long paper-run actions so the browser request does not block.
- `continue_paper_validation` is an executable default action: it records the current Alpha validation facts into per-strategy `StrategyAlphaSnapshot` records instead of returning a skipped/no-op response.
- After the current trading day's Alpha snapshot is recorded, the paper action plan switches to `hold_until_next_session` so the default path waits for the scheduler instead of rewriting the same snapshot.
- The `hold_until_next_session` action now includes Alpha sampling forecast and the next actionable scheduler sample, so waiting states still show how many paper sessions remain and when the next useful sample is expected.
- The `hold_until_next_session` action now also surfaces triggered exit samples expected on the next paper run, using the same order-projected as-of position view as the Daily Report so closed-trade sample progress is visible from the default action plan.
- Paper Action Plan items now expose structured `projected_gate_impacts`, so the UI can show concrete next-run Alpha progress such as `closed trades +2, remaining 3 -> 1` instead of burying that information in evidence strings.
- Latest incremental verification on 2026-06-19: executing the default `continue_paper_validation` action persisted registered-strategy Alpha snapshots for trading day `2026-06-17` (`deterministic_watchlist_v1` and `moving_average_cross`) and advanced the next primary action to `hold_until_next_session`.
- The Daily Report now exposes the next effective paper sample separately from the next raw cron trigger through `scheduler_next_actionable_run_at`, `scheduler_next_actionable_trading_day`, `estimated_sessions_to_alpha_ready`, and `limiting_alpha_gate`, so operators can see when the next candidate/order sample will actually be collected.
- The Daily Report now separates total generated candidates from actionable, ordered, and dismissed candidates through `actionable_candidate_count`, `ordered_candidate_count`, and `dismissed_candidate_count`, so paper operators can distinguish tradable signals from filtered research outputs.
- The Daily Report now includes quantified open Alpha gate gaps through `open_alpha_gates`, so operators can see current/required/remaining samples for blockers such as filled orders and closed trades without leaving the paper trading workspace.
- The Daily Report now reports latest/average/consecutive expectancy from strategy-level Alpha Validation, not account-level review trend, so positive portfolio PnL cannot mask a strategy that has not produced closed-trade expectancy yet.
- The Daily Report now includes an `exit_watchlist` from current open paper positions, showing take-profit/stop-loss triggers, return percentage, unrealized PnL, and next eligible exit quantity so closed-trade sample collection is visible before the next daily loop even when the report uses an as-of trading-day view.
- The Daily Report now uses stored paper execution marks for operational exit monitoring instead of blocking on live OpenBB/Yahoo quote calls; slower summary endpoints no longer prevent the report from rendering in the paper workspace.
- Latest incremental verification on 2026-06-18: `GET /api/mvp/paper-trading/summary` now defaults to the stored effective-trading-day paper state and only refreshes live quote marks when `refresh_quotes=true`, keeping the Paper Trading workspace on a fast loading path while preserving optional mark-to-market refreshes.
- OpenBB optional data access now circuit-breaks runtime quote/history/fundamental failures inside the request and falls back through the provider abstraction, so research data outages do not turn the paper trading dashboard into a 500.
- Executing `hold_until_next_session` returns `status: waiting` with scheduler context instead of a skipped/no-op response.
- Scheduler status distinguishes the next cron trigger from the next actionable market sample through `next_run_will_execute`, `next_run_execution_gate`, `next_run_trading_day`, `next_actionable_run_at`, and `next_actionable_trading_day`.
- Current scheduler runtime shows the next cron trigger will be guarded as `market_closed`, while the next actionable paper sample is `2026-06-16T06:30:00+08:00` for trading day `2026-06-15`.
- Scheduled paper runs persist `scheduler_decision` events for guarded skips, executed runs, and failed execution attempts, so daily automation decisions remain auditable even when no broker-facing action occurs or an internal paper loop error is raised.
- The operations status API and Paper Trading workspace now surface the latest persisted `scheduler_decision`, including outcome, trading day, reason, timestamp, and summary.
- Alpha snapshot history is filtered through the current effective market trading day, so legacy future-dated simulation snapshots do not drive the latest readiness view.
- `collect_post_limit_sample` uses the normal paper trading loop with a controlled `force_new_sample` flag, so a post-limit sample can create a new run even when the same trading day already has a completed run.
- Daily paper loop early-return recovery now backfills registered Alpha snapshots and Strategy Competition snapshots when a trading day already has a completed run but those control-plane artifacts are missing. This keeps old or interrupted runs from leaving the action plan stuck on `continue_paper_validation`.
- Strategy Registry now reads per-strategy backtest history, prioritizes successful real-market backtests over the latest mock/deterministic fallback, and converts only positive-return backtests into read-only ranking evidence.
- `moving_average_cross` is now connected to the controlled paper runtime after positive real-market backtest evidence. Daily paper candidate generation routes it through `StrategyRegistry -> StrategyExecutionBinding -> StrategyEngine -> RiskEngine -> ExecutionEngine -> EventLedger`; it consumes provider price history to create 20/50 SMA `MarketEvent` metadata and may produce paper orders, while live execution remains disabled.
- Each daily paper run now records `StrategyAlphaSnapshot` evidence for every registered paper runtime strategy, currently `deterministic_watchlist_v1` and `moving_average_cross`, so Alpha gate evidence is no longer limited to the default strategy.
- Alpha validation now computes runtime expectancy from each strategy's own closed paper trades instead of reusing account-level review expectancy, so strategy competition is not credited with another strategy's PnL.
- Strategy Registry now consumes registered runtime Alpha evidence for connected paper strategies, so Strategy Competition can see actual paper review days and filled-order counts instead of leaving connected catalog strategies at zero samples.
- Strategy Competition marks positive catalog backtests as `connect_to_paper_runtime` work, while keeping negative or flat backtests in the lab and still blocking all catalog strategies from allocation until they are connected to the paper runtime and hot-swap path.
- Daily paper candidate selection records every generated candidate as a `trade_explanation` core event; when backtest evidence exists it includes backtest metrics, otherwise it records evidence count, quote source, diversification context, and the candidate ranking score breakdown.
- Daily paper candidates now persist and return `strategy_id`; manual buys launched from a candidate carry that same strategy id into the paper order payload, preserving candidate -> order -> Alpha attribution.
- Paper orders now persist optional `candidate_id`; automatic candidate orders and candidate-launched manual buys carry the originating candidate id, so candidate rationale can be traced through order execution and later PnL review.
- Automatic paper exit orders now inherit the latest linked entry candidate id, preserving candidate attribution through closed-trade realized PnL instead of stopping at the opening order.
- Strategy attribution now prefers order-linked `candidate_id` when matching candidate scores to observed PnL, falling back to ticker-level matching only for older records without candidate linkage.
- EventLedger replay now exposes `trade_explanation` details in the API and Paper Trading workspace, including decision, strategy id, explanation, evidence, and backtest return.
- `GET /api/mvp/paper-trading/market-events` now exposes a user-facing Market Event Center over persisted `CoreEventLog` data. Operators can filter by ticker, then see the `MarketEvent` summary, strategy id, confidence, impact score, source, downstream `TradeIntent`, `RiskDecision`, `OrderState`, explanation, evidence, and `correlation_id`.
- The Paper Trading workspace now displays the strategy source for each candidate, so operators can see which registry-controlled strategy generated a tradable paper signal before submitting a mock order.
- The Paper Trading workspace now surfaces the `final_score` candidate ranking evidence as a readable ranking score in the Event Ledger review card.
- The Paper Trading workspace now opens with a purpose-based SPCX/INTC onboarding guide and a Registry-backed strategy source panel. The UI explicitly labels `deterministic_watchlist_v1` and `moving_average_cross` as controlled baseline research strategies, not proven profitable Alpha; each strategy still needs backtest evidence, paper samples, PnL, risk, and event-ledger attribution before promotion.
- The Paper Trading workspace is split into professional workflow views: Overview, Events & AI, Candidates & Simulation, Risk & Review, and Operations. The Events & AI view includes concrete EventLedger topic flow, correlation id, a Market Event Center for selected tickers such as SPCX and INTC, human-readable event explanations, per-evidence source/title/summary/url details, optional raw payload content, AI/LangGraph/LLM analysis boundary, latest `trade_explanation` evidence, and a selectable OHLC candlestick panel.
- Strategy attribution now reads `trade_explanation` events and links candidate `final_score` evidence to ticker-level observed PnL diagnostics.
- Strategy attribution ticker diagnostics are sorted by observed PnL impact first, so review screens focus on the ticker that most affected results instead of alphabetical order.
- Strategy Lab now labels whether candidate score direction and observed PnL are `aligned`, `inverted`, or still unresolved, making score/PnL divergence visible during review.
- Alpha validation now treats score/PnL inversion as a quality blocker: any ticker with inverted candidate score direction versus observed PnL adds `score_pnl_inversion_review`, exposes `score_pnl_inversion_count`, and blocks `paper_validated` until reviewed.
- The paper action plan now turns `score_pnl_inversion_review` into a concrete `review_score_pnl_inversion` action, including inverted tickers such as AMZN in the evidence. Executing that primary action writes a `strategy_review` CoreEventLog audit event and returns `review_required` instead of placing trades or changing risk limits; the next plan consumes the recorded review event so the same score/PnL inversion is not repeatedly promoted as the primary action.
- `GET /api/mvp/paper-trading/strategy-reviews` reads persisted `strategy_review` CoreEventLog audit events and the Paper Trading workspace displays those records next to the Action Plan, so score/PnL quarantine evidence is reviewable without querying the generic event ledger.
- Daily candidate generation now consumes required `strategy_review` score/PnL inversion events and excludes those tickers from new buy candidates while the review remains unresolved; existing position exit handling remains active.
- Score/PnL inversion quarantine is now strategy-scoped. Legacy review events without a `strategy_id` are treated as `deterministic_watchlist_v1` reviews, so they still block the default evidence-scoring strategy from reusing inverted tickers while allowing `moving_average_cross` to test its independent moving-average hypothesis on the same ticker universe.
- Alpha validation now counts only unreviewed score/PnL inversion tickers as open blockers, so a recorded `strategy_review` quarantine lets the system continue collecting clean paper samples without reintroducing the isolated ticker.
- Paper Trading summary now defaults to the effective market trading day, matching Daily Report and Alpha gates, so non-trading-day manual reviews do not appear as the current paper review by default.
- Candidate-only event chains (`MarketEvent -> StrategyInput -> TradeIntent`) are treated as replayable evidence; repair is reserved for missing ledgers or broken risk/order chains.
- Latest verified paper run: `0d8a4017-67c4-4a4c-8f09-d257cc74770c`, trading day `2026-06-12`, status `completed`, 7 candidates, 28 replayable core events, including 7 `trade_explanation` events.
- Latest operations status: `ready`, no runtime blockers, event ledger ready.
- Latest executed score/PnL inversion review recorded `paper_action:review_score_pnl_inversion:AAPL,AMZN,META,MSFT,NVDA:2:strategy_review`; after that runtime Alpha gate progress is 6/10 and `score_pnl_inversion_count=0`.
- Latest Alpha gate state: 6/10 gates passed; still collecting review days, consecutive positive expectancy days, filled-order sample, and closed-trade sample.
- Latest filtered Alpha snapshot: trading day `2026-06-12`, `validation_level=collecting`, blockers `review_day_sample`, `consecutive_positive_expectancy`, `filled_order_sample`, `closed_trade_sample`.
- Latest paper risk review: hold `max_daily_orders` at 10; the latest post-limit sample completed without a new buy `max_daily_orders` rejection.
- Current recommended action after the current-day snapshot is recorded: hold until the next scheduled paper run; live limits remain unchanged.

中文对应事实：

- API、Web、PostgreSQL、Redis 已通过 Docker Compose 一起运行。
- `GET /api/mvp/data-sources/status` 在当前 Docker 运行态返回 `provider_mode=hybrid`，并显示 Mock、SEC EDGAR、OpenBB 均可用。
- `GET /api/mvp/ai/status` 会返回 LangGraph 投研 workflow 可用状态和 OpenAI-compatible 投研 LLM 状态。2026-06-15 当前 Docker 运行态 Research LLM 已配置且可用（`configured=true`、`available=true`，模型 `mimo-v2.5-pro`）；`ai_generates_trade_intent`、`ai_influences_risk`、`ai_calls_execution` 均为 `false`。
- `GET/PUT /api/mvp/runtime-settings` 支撑 Web 设置页，运行人员可在运行态调整数据模式、SEC EDGAR User-Agent、LEAN 回测超时、OpenAI Research LLM 模型/Base URL/超时，并保存或清除 OpenAI API key。已保存的 API key 只供后端使用，不会在 API 响应中回显；Scheduler 启动和 Redis 连接仍从环境变量读取。
- `GET /api/mvp/strategy-lab/status` 现在会展示 Docker CLI、Docker Compose、Docker engine、LEAN CLI、本地缓存的 `quantconnect/lean:latest` 和 vectorbt 就绪状态。当前 Docker 运行态已缓存 QuantConnect LEAN 引擎镜像。
- `POST /api/mvp/strategy-lab/backtests` 已在 LEAN 引擎运行态验证：系统会把 OpenBB/yfinance 真实历史 K 线注入为 LEAN `PythonData` custom data。最新验证 LEAN run `20260615T051211211740Z-moving_average_cross` 返回 `data_source=openbb_yfinance`、`data_quality=real_market_data`、`uses_real_market_data=true`、`total_net_profit=71.330%`、`sharpe_ratio=2.114`、`drawdown=20.300%`、`total_trades=3`。
- `deterministic_watchlist_v1` 仍使用 vectorbt 做 active strategy 历史 replay；最新验证 vectorbt/OpenBB run `20260615T050310967734Z-deterministic_watchlist_v1` 返回 `data_quality=real_market_data`、`total_net_profit=38.60%`、`sharpe_ratio=1.45`、`drawdown=17.91%`、`total_trades=8`。vectorbt 仍只属于研究/回测层，不替代运行时 Trading Core。
- `POST /api/mvp/research` 只有在 OpenAI-compatible LLM 调用成功时才返回 `status=complete_llm`；未配置 key 或供应商失败时，同一接口会回退到确定性的 LangGraph 投研输出，并保持 `requires_human_review=true`。Web AI 侧栏现在会显示 `LLM 可用` 或 `本地规则`，本地规则结果会标注为 `本地规则`，避免误以为已经使用 LLM。
- Web AI 侧栏现在可以收起为紧凑 AI 入口，也可以展开恢复完整面板；展开后的 prompt 仍调用真实 `/api/mvp/research` 路径，并可将研究输出保存为笔记。
- `POST /api/mvp/paper-trading/action-plan/execute-primary` 会同步执行快速安全动作，并将较长的 paper run 动作排入后台，避免浏览器请求阻塞。
- `continue_paper_validation` 已是可执行默认动作：它会把当前 Alpha 验证事实分别写入各策略的 `StrategyAlphaSnapshot`，不再返回 skipped/no-op。
- 当前交易日 Alpha 快照记录完成后，paper action plan 会切换到 `hold_until_next_session`，默认路径等待调度器，不再重复改写同一张快照。
- `hold_until_next_session` 动作现在会带上 Alpha 样本预测和下一次有效调度采样，因此等待状态也能显示还需要多少次 paper sessions、下一次有效样本预计何时发生。
- `hold_until_next_session` 动作现在也会展示下一次 paper run 预计触发的退出样本，并复用 Daily Report 同一套基于订单投影的 as-of 持仓口径，因此默认行动计划里也能看到闭环交易样本会如何推进。
- Paper Action Plan 现在会返回结构化 `projected_gate_impacts`，因此 Web UI 可以直接展示下一次运行预计推进哪些 Alpha 门禁，例如 `闭环交易 +2 笔，剩余 3 到 1 笔`，不再把这类关键信息藏在 evidence 字符串里。
- 2026-06-19 最新增量验证：执行默认 `continue_paper_validation` 动作后，系统已为交易日 `2026-06-17` 写入已注册策略的 Alpha 快照（`deterministic_watchlist_v1` 和 `moving_average_cross`），下一主动作已切换为 `hold_until_next_session`。
- Daily Report 现在会把“下一次有效 paper 采样”和“下一次原始 cron 触发”分开展示，通过 `scheduler_next_actionable_run_at`、`scheduler_next_actionable_trading_day`、`estimated_sessions_to_alpha_ready` 和 `limiting_alpha_gate` 说明下一批候选/订单样本实际何时采集。
- Daily Report 现在会把总生成候选、可下单候选、已下单候选和已过滤候选分开，通过 `actionable_candidate_count`、`ordered_candidate_count` 和 `dismissed_candidate_count` 区分真实可交易信号与被过滤的研究输出。
- Daily Report 现在会通过 `open_alpha_gates` 展示未通过 Alpha 门禁的当前值、目标值和剩余缺口，因此操作者不离开模拟盘工作台也能看到成交订单、闭环交易等 blocker 还差多少样本。
- Daily Report 现在的最新/平均/连续期望改用策略级 Alpha Validation 口径，不再用账户级复盘趋势；因此组合浮盈为正也不能掩盖某个策略尚未形成闭环交易期望的事实。
- Daily Report 现在会通过 `exit_watchlist` 展示当前开放模拟持仓的止盈/止损触发、收益率、浮动盈亏和下一次可退出数量；即使日报其他字段采用 as-of 交易日口径，下一次日循环能补哪些闭环交易样本也会提前可见。
- Daily Report 现在使用已记录的 paper execution mark 做运营退出监控，不再阻塞等待 live OpenBB/Yahoo 报价；较慢的 summary 接口也不会阻止模拟盘工作台先渲染今日简报。
- 2026-06-18 最新增量验证：`GET /api/mvp/paper-trading/summary` 现在默认读取已记录的有效交易日模拟盘状态；只有显式传入 `refresh_quotes=true` 时才刷新实时行情标记，因此模拟盘工作台走快速加载路径，同时仍保留可选的实时盯市刷新能力。
- OpenBB 可选数据访问现在会在单次请求内对 quote/history/fundamental 运行时失败熔断，并通过数据源抽象降级，因此研究数据源故障不会把模拟盘页面打成 500。
- 执行 `hold_until_next_session` 会返回 `status: waiting` 和调度器上下文，不再返回 skipped/no-op。
- Scheduler 状态会用 `next_run_will_execute`、`next_run_execution_gate`、`next_run_trading_day`、`next_actionable_run_at`、`next_actionable_trading_day` 区分“下一次 cron 触发”和“下一次真正可采样的美股交易日”。
- 当前调度器运行态显示，下一次 cron 会因 `market_closed` 守门跳过，而下一次真正有效的 paper 采样时间是 `2026-06-16T06:30:00+08:00`，对应交易日 `2026-06-15`。
- 定时 paper run 已对守门跳过、真实执行和执行失败三种结果都写入 `scheduler_decision` 事件，因此每日自动化决策即使没有触发券商侧动作或内部 paper loop 报错，也可以审计。
- 运行健康 API 和模拟盘工作台已展示最新落库的 `scheduler_decision`，包括结果、交易日、原因、时间和摘要。
- Alpha snapshot 历史会按当前有效美股交易日过滤，旧的未来日期模拟快照不会再影响最新 readiness 视图。
- `collect_post_limit_sample` 仍走同一条 paper trading loop，只通过受控的 `force_new_sample` 标记生成限额更新后的新样本。
- 每日 paper loop 的已完成运行早返回路径现在会补写已注册策略 Alpha 快照和 Strategy Competition 快照；如果旧版本或中断导致某个交易日有 completed run 但缺少控制平面证据，系统会自动补齐，不会让行动计划长期卡在 `continue_paper_validation`。
- Strategy Registry 现在会按策略读取回测历史，优先采用真实市场成功回测，而不是被最新 mock/deterministic fallback 覆盖，并且只把正收益回测转成只读排名证据。
- `moving_average_cross` 已在真实市场回测为正后接入受控 paper runtime。每日 paper 候选生成会通过 `StrategyRegistry -> StrategyExecutionBinding -> StrategyEngine -> RiskEngine -> ExecutionEngine -> EventLedger` 路由该策略；它会消费 provider 价格历史生成 20/50 SMA `MarketEvent` 元数据，并可产生模拟盘订单，但 live 执行仍被禁用。
- 每次每日 paper run 现在都会为所有已注册 paper runtime 策略分别记录 `StrategyAlphaSnapshot` 证据，目前包括 `deterministic_watchlist_v1` 和 `moving_average_cross`，因此 Alpha 门禁证据不再只覆盖默认策略。
- Alpha 验证现在会用各策略自己的已闭环模拟交易计算运行期望，不再复用账户级复盘 expectancy，因此策略竞争不会把其他策略的盈亏算到自己名下。
- Strategy Registry 现在会消费已注册 runtime 策略的 Alpha 证据，因此 Strategy Competition 可以看到已接入 paper 策略的真实复盘天数和成交订单数，不再把已接入的目录策略显示为 0 样本。
- Strategy Competition 会把正收益目录回测标记为 `connect_to_paper_runtime` 工作项；负收益或持平回测继续留在 lab，且所有目录策略在接入 paper runtime 和热切换路径前仍禁止进入资金分配。
- 每日 paper 候选筛选会把每一个生成候选记录为 `trade_explanation` core event；有回测证据时写入回测指标，没有回测时写入证据数量、报价源、分散度上下文和候选排序分数拆解。
- 每日 paper 候选现在会持久化并返回 `strategy_id`；从候选发起的手动模拟买入会把同一个策略 ID 带入 paper order payload，保留候选 -> 订单 -> Alpha 归因链。
- Paper order 现在会持久化可选的 `candidate_id`；自动候选订单和从候选发起的手动模拟买入都会带上原始候选 ID，因此候选理由可以继续追踪到订单执行和后续盈亏复盘。
- 自动 paper 退出订单现在会继承最近一次有关联的入场候选 ID，因此候选归因可以穿透到闭环交易的已实现盈亏，而不是停在开仓订单。
- 策略归因现在会优先使用订单关联的 `candidate_id` 匹配候选评分与观测盈亏；只有老数据没有候选关联时才退回 ticker 级匹配。
- EventLedger replay 现在会在 API 和模拟盘工作台展示 `trade_explanation` 明细，包括决策、策略 ID、解释、证据和回测收益。
- `GET /api/mvp/paper-trading/market-events` 现在会基于已落库的 `CoreEventLog` 暴露面向用户的市场事件中心。运行人员可以按 ticker 筛选，并看到 `MarketEvent` 摘要、策略 ID、置信度、影响分、来源、后续 `TradeIntent`、`RiskDecision`、`OrderState`、解释、证据和 `correlation_id`。
- 模拟盘工作台现在会显示每个候选的策略来源，因此操作者在提交模拟订单前可以看到该可交易信号来自哪个 Registry 控制的策略。
- 模拟盘工作台现在会把 `final_score` 候选排序证据显示为事件账本复盘卡里的可读排序分数。
- 模拟盘工作台现在进入页面先展示基于 SPCX/INTC 的按目的上手向导，并展示由 Strategy Registry 驱动的策略来源面板。页面会明确说明 `deterministic_watchlist_v1` 和 `moving_average_cross` 是受控研究基线策略，不是已经证明盈利的成熟 Alpha；策略晋级仍需要回测证据、模拟盘样本、盈亏、风控和事件账本归因共同证明。
- 模拟盘工作台现在按专业工作流拆成“总览 / 事件与AI / 候选与模拟 / 风控与复盘 / 运行维护”。其中“事件与AI”包含具体 EventLedger topic 流和 correlation id、可按 SPCX/INTC 等标的切换的市场事件中心、人可读的事件解读、逐条证据的来源/标题/摘要/链接、可选原始 payload、AI/LangGraph/LLM 分析边界、最新 `trade_explanation` 证据，以及 OHLC K线面板。
- 评分/盈亏背离隔离现在按策略生效。历史没有 `strategy_id` 的复盘事件默认视为 `deterministic_watchlist_v1` 复盘，因此仍会阻止默认证据评分策略复用背离 ticker，但不会阻止 `moving_average_cross` 在同一 ticker universe 上验证独立的均线假设。
- 策略归因现在会读取 `trade_explanation` 事件，并把候选 `final_score` 证据关联到 ticker 级观测盈亏诊断。
- 策略归因的 ticker 诊断现在会优先按观测盈亏影响排序，因此复盘页面先展示最影响结果的标的，而不是按字母顺序展示。
- 策略实验室现在会标记候选评分方向与观测盈亏是 `aligned`、`inverted` 还是仍待验证，让评分和盈亏背离在复盘时直接可见。
- Alpha 验证现在会把评分/盈亏反向视为质量阻断：任何 ticker 的候选评分方向与观测盈亏相反，都会加入 `score_pnl_inversion_review`，暴露 `score_pnl_inversion_count`，并在复盘前阻止进入 `paper_validated`。
- Paper action plan 现在会把 `score_pnl_inversion_review` 转成具体的 `review_score_pnl_inversion` 行动项，并在证据里列出 AMZN 等评分反向标的。执行这个首要动作会写入一条 `strategy_review` CoreEventLog 审计事件，并返回 `review_required`，不会自动下单或改风控；下一轮计划会消费这条已记录复盘事件，避免同一评分/盈亏背离反复被提升为主动作。
- `GET /api/mvp/paper-trading/strategy-reviews` 现在会读取已落库的 `strategy_review` CoreEventLog 审计事件，模拟盘工作台也会把这些记录展示在行动计划旁边，因此评分/盈亏隔离证据不需要再去通用事件账本里翻。
- 每日候选生成现在会消费仍为 `required` 的 `strategy_review` 评分/盈亏背离事件，并在复盘未解除前把这些 ticker 从新的买入候选中排除；已有持仓的退出处理仍继续生效。
- Alpha 验证现在只把尚未复盘隔离的评分/盈亏背离 ticker 计为开放阻断；已记录 `strategy_review` 隔离事件后，系统可以继续收集干净的 paper 样本，同时不重新引入被隔离的 ticker。
- 模拟盘 summary 现在默认使用有效美股交易日口径，与 Daily Report 和 Alpha 门禁一致，因此非交易日手动复盘不会默认显示为当前 paper review。
- 仅包含候选和 `TradeIntent` 的事件链会被视为可回放证据；repair 只用于缺失账本或损坏的风控/订单链。
- 最新已验证 paper run：`0d8a4017-67c4-4a4c-8f09-d257cc74770c`，交易日 `2026-06-12`，状态 `completed`，7 个候选，28 条可回放 core events，其中包含 7 条 `trade_explanation` 事件。
- 最新运行健康状态：`ready`，无运行阻断，事件账本可回放。
- 最新已执行评分/盈亏背离复盘记录：`paper_action:review_score_pnl_inversion:AAPL,AMZN,META,MSFT,NVDA:2:strategy_review`；执行后运行态 Alpha gate 为 6/10，`score_pnl_inversion_count=0`。
- 最新 Alpha 门禁：6/10 通过；仍需继续收集复盘天数、连续正期望天数、成交订单样本和闭环交易样本。
- 最新过滤后的 Alpha 快照：交易日 `2026-06-12`，`validation_level=collecting`，阻断项为 `review_day_sample`、`consecutive_positive_expectancy`、`filled_order_sample`、`closed_trade_sample`。
- 最新 Paper 风险评审：保持 `max_daily_orders=10`；最新限额后样本没有新的买入侧 `max_daily_orders` 拒单。
- 当前推荐动作：当前日快照已记录后等待下一次定时 paper run；live 限额不变。

## Architecture / 系统架构

```text
Web UI
  -> FastAPI API Layer
  -> Strategy Registry / Strategy Runtime
  -> Trading Core
       -> Event Bus
       -> Strategy Engine
       -> Risk Engine
       -> Execution Engine
       -> Event Ledger
  -> Paper Trading Account and Reviews
  -> Strategy Lab / Backtests / Evaluation
  -> AI Research Workflow
  -> PostgreSQL + Redis
```

Core rules:

核心规则：

- `StrategyRegistry` is the strategy entry point.
- `TradeIntent` must pass through risk before execution.
- `ExecutionEngine` records order state transitions.
- Production events are persisted through the event ledger.
- AI is for research, explanation, and event structuring, not direct order decisions.
- LangGraph orchestrates the AI research workflow, not order execution.
- OpenAI-compatible LLM providers can optionally generate structured research explanations through Responses or Chat Completions when an API key is saved in runtime settings or provided through `AI_STOCKS_OPENAI_API_KEY` / `OPENAI_API_KEY`; without a key, the same endpoint falls back to deterministic LangGraph research output.
- OpenBB provides market-data/research access when available, is warmed during API startup for thread-safe FastAPI usage, and does not bypass the data-provider abstraction or execution path.
- LEAN and vectorbt are research/backtest tools, not live execution paths.

中文说明：

- `StrategyRegistry` 是策略进入系统的入口。
- `TradeIntent` 必须先经过风控，才能进入执行。
- `ExecutionEngine` 记录订单状态机变化。
- 生产事件必须写入事件账本。
- AI 只用于研究、解释和事件结构化，不直接生成交易指令。
- LangGraph 用于编排 AI 投研 workflow，不用于订单执行。
- 在运行配置中保存 API key，或通过 `AI_STOCKS_OPENAI_API_KEY` / `OPENAI_API_KEY` 提供 key 后，OpenAI-compatible LLM 可通过 Responses 或 Chat Completions 生成结构化投研解释；未配置 key 时，同一接口会回退到确定性的 LangGraph 投研输出。
- OpenBB 在可用时提供行情和研究数据能力，并在 API 启动阶段预热以适配 FastAPI 线程池；它不能绕过数据源抽象层或交易执行路径。
- LEAN 和 vectorbt 只用于研究/回测，不进入实盘执行路径。

## Trading Core / 自研交易内核

VelaQuant has its own Trading Core. It is implemented in `apps/api/app/trading_core/` and is not provided by LEAN, OpenBB, LangGraph, or the frontend.

VelaQuant 有自己的 Trading Core。它位于 `apps/api/app/trading_core/`，不是 LEAN、OpenBB、LangGraph 或前端页面提供的能力。

Trading Core modules:

Trading Core 模块：

```text
apps/api/app/trading_core/
  engine.py           TradingEngine orchestration
  event_bus.py        EventEnvelope, event topics, in-memory and Redis stream event bus
  events.py           MarketEvent and StrategyInputEvent schemas
  strategy_engine.py  StrategyEngine wrapper for deterministic strategy output
  strategy.py         TradeIntent, deterministic watchlist, and moving-average strategy contracts
  risk.py             RiskEngine and RiskLimits
  execution.py        ExecutionEngine, CoreOrder, OrderState, execution adapter boundary
  portfolio.py        PortfolioState and positions
```

The core execution sequence is:

核心执行顺序是：

```text
MarketEvent
  -> StrategyInputEvent
  -> TradeIntent
  -> RiskDecision
  -> OrderState
  -> EventLedger
```

Important boundary:

重要边界：

- `TradingEngine` requires a registry-provided `StrategyExecutionBinding`; a raw strategy engine should not be wired directly into execution.
- `RiskEngine` is inside the Trading Core path and must approve/reject `TradeIntent` before order state is recorded.
- `ExecutionEngine` owns order-state transitions for the core path.
- `EventLedger` persists runtime core events for audit and replay.
- LEAN/vectorbt are research and backtest tools only.
- OpenBB is data/research access only.
- LangGraph is research workflow orchestration only.
- AI does not generate executable `TradeIntent` and does not call `ExecutionEngine`.

中文说明：

- `TradingEngine` 要求使用由 registry 提供的 `StrategyExecutionBinding`，不能把裸 strategy engine 直接接进执行链。
- `RiskEngine` 位于 Trading Core 主路径中，必须先批准或拒绝 `TradeIntent`，随后才记录订单状态。
- `ExecutionEngine` 负责核心路径上的订单状态转换。
- `EventLedger` 将运行时 core events 持久化，用于审计和回放。
- LEAN/vectorbt 只用于研究和回测。
- OpenBB 只用于数据和研究访问。
- LangGraph 只用于投研 workflow 编排。
- AI 不生成可执行 `TradeIntent`，也不调用 `ExecutionEngine`。

## Tech Stack / 技术栈

Backend / 后端：

- FastAPI
- Pydantic
- SQLModel
- PostgreSQL
- Redis Streams
- APScheduler
- LangGraph
- OpenAI-compatible LLM integration for optional research-only explanations through Responses or Chat Completions
- OpenBB
- vectorbt
- QuantConnect LEAN CLI integration for research workflows
- pandas / numpy
- pandas-market-calendars
- pytest

Backend support libraries / 后端支撑库：

- `psycopg`: PostgreSQL driver.
- `httpx`: HTTP client used by data and provider integrations.
- `OpenAI-compatible LLM`: optional research-only LLM integration behind the existing AI workflow through Responses or Chat Completions.
- `openpyxl`: spreadsheet import support.
- `pydantic-settings`: environment-driven runtime configuration.

中文说明：

- `psycopg`：PostgreSQL 驱动。
- `httpx`：数据源和 provider 集成使用的 HTTP 客户端。
- `OpenAI-compatible LLM`：挂在现有 AI workflow 后面、通过 Responses 或 Chat Completions 接入的可选投研解释 LLM。
- `openpyxl`：表格导入能力。
- `pydantic-settings`：环境变量驱动的运行配置。

Frontend / 前端：

- Next.js
- React
- TypeScript
- Playwright tests

Runtime / 运行环境：

- Docker Compose
- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3000`

## AI Workflow / AI 工作流

VelaQuant uses LangGraph in `apps/api/app/ai/workflow.py` to run the research assistant workflow behind `POST /api/mvp/research`. When an OpenAI-compatible API key is saved in runtime settings or provided through the environment, the workflow can call Responses or Chat Completions through `apps/api/app/ai/llm.py` for structured research explanations. When no key is configured, the same endpoint returns deterministic research output.

VelaQuant 在 `apps/api/app/ai/workflow.py` 中使用 LangGraph，支撑 `POST /api/mvp/research` 背后的投研助手 workflow。在运行配置中保存 OpenAI-compatible API key 或通过环境变量提供 key 后，workflow 可通过 `apps/api/app/ai/llm.py` 调用 Responses 或 Chat Completions 生成结构化投研解释；未配置 key 时，同一接口返回确定性投研输出。

The Web AI sidecar reads `GET /api/mvp/ai/status` and shows whether the current research result is LLM-backed (`LLM 可用` / `LLM 已生成`) or local deterministic workflow output (`本地规则`). This status is informational only and does not affect strategy, risk, or execution.

Web AI 侧栏会读取 `GET /api/mvp/ai/status`，并显示当前研究结果是 LLM 支撑（`LLM 可用` / `LLM 已生成`）还是本地确定性 workflow 输出（`本地规则`）。这个状态只用于投研可见性，不影响策略、风控或执行。

Current workflow behavior:

当前 workflow 行为：

- Input: ticker, user question, and structured evidence items.
- Output: summary, bull case, bear case, watch items, and a trade-plan draft.
- Optional LLM mode: Responses or Chat Completions returns structured JSON and is forced back into a human-review-only `TradePlanDraft`.
- If evidence is missing, the workflow returns an `insufficient_evidence` result.
- The trade-plan draft is explicitly not an executable order.

中文说明：

- 输入：ticker、用户问题和结构化证据项。
- 输出：摘要、多头观点、空头风险、观察项和交易计划草稿。
- 可选 LLM 模式：Responses 或 Chat Completions 返回结构化 JSON，并被强制收敛为仅供人工复核的 `TradePlanDraft`。
- 如果证据不足，workflow 返回 `insufficient_evidence`。
- 交易计划草稿不是可执行订单。

Current boundary:

当前边界：

- LangGraph is used for research workflow orchestration.
- OpenAI-compatible LLM integration is optional and research-only.
- It does not generate `TradeIntent`.
- It does not call `ExecutionEngine`.
- It does not bypass `StrategyRegistry` or `RiskEngine`.

中文说明：

- LangGraph 当前用于投研 workflow 编排。
- OpenAI-compatible LLM 集成是可选的，且只用于投研解释。
- 它不生成 `TradeIntent`。
- 它不调用 `ExecutionEngine`。
- 它不能绕过 `StrategyRegistry` 或 `RiskEngine`。

## Data Sources / 数据源

VelaQuant uses a provider abstraction for market and research data. The current data layer can run safely with mock data for development and can use OpenBB when the package and its upstream data access are available.

VelaQuant 通过统一的数据源抽象层读取行情和研究数据。当前系统可以在开发环境使用 Mock 数据安全运行，也可以在 OpenBB 包和上游数据访问可用时调用 OpenBB。

Current data-source roles:

当前数据源职责：

- OpenBB: quote, historical price, and fundamentals research access when available.
- SEC EDGAR: filing evidence and regulatory document metadata.
- MockProvider: deterministic local development and test data.

中文说明：

- OpenBB：在可用时提供报价、历史价格和基本面研究数据。
- SEC EDGAR：提供公告、财报文件和监管披露证据。
- MockProvider：用于本地开发和测试的确定性数据。

OpenBB is part of the data/research layer. It is not a broker, not a risk engine, and not an execution adapter.

OpenBB 属于数据/研究层，不是券商接口、不是风控引擎，也不是执行适配器。

## Local Startup / 本地启动

Start the full stack:

启动完整 Docker 环境：

```powershell
docker compose up --build
```

Current Windows workstation note: Docker Desktop WSL data was moved from `%LOCALAPPDATA%\Docker\wsl` to `D:\Docker\DockerDesktopWSL\wsl`; the original path is a junction to the D: drive location so Docker Desktop can keep using its normal path.

当前 Windows 工作站备注：Docker Desktop WSL 数据已从 `%LOCALAPPDATA%\Docker\wsl` 迁移到 `D:\Docker\DockerDesktopWSL\wsl`；原路径保留为指向 D 盘位置的 junction，因此 Docker Desktop 仍可按默认路径运行。

Check API health:

检查 API 健康状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Open the app:

打开前端：

```text
http://127.0.0.1:3000
```

## Useful Endpoints / 常用接口

```text
GET  /health
GET  /api/mvp/dashboard
GET  /api/mvp/paper-trading/summary
GET  /api/mvp/paper-trading/daily-report
POST /api/mvp/paper-trading/daily-run
GET  /api/mvp/paper-trading/action-plan
POST /api/mvp/paper-trading/action-plan/execute-primary
GET  /api/mvp/paper-trading/event-ledger
GET  /api/mvp/market/history/{ticker}
GET  /api/mvp/strategy-lab/alpha-gates
GET  /api/mvp/strategy-lab/alpha-snapshots
GET  /api/mvp/strategy-lab/evaluation
POST /api/mvp/strategy-lab/backtests
```

`GET /api/mvp/paper-trading/summary` defaults to the fast stored paper view. Use `?refresh_quotes=true` only when the operator explicitly wants to refresh live quote marks before reading the summary.

`GET /api/mvp/paper-trading/summary` 默认返回快速的已记录模拟盘视图。只有操作者明确需要先刷新实时行情标记时，才使用 `?refresh_quotes=true`。

## Development Commands / 开发命令

Backend tests:

后端测试：

```powershell
docker compose exec -T api python -m pytest -q
```

Frontend type check:

前端类型检查：

```powershell
docker compose exec -T web npm run lint
```

Run a focused paper action:

执行当前推荐的模拟盘动作：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/mvp/paper-trading/action-plan/execute-primary
```

Quick actions return `status: completed`. When the primary action is `continue_paper_validation`, the result contains per-strategy Alpha validation snapshots. When the primary action is `hold_until_next_session`, the result returns `status: waiting` plus scheduler context. Long paper-run actions return `status: queued` and write their final outcome to `GET /api/mvp/paper-trading/runs`.

快速动作返回 `status: completed`。当主动作是 `continue_paper_validation` 时，结果会包含各策略的 Alpha 验证快照。当主动作是 `hold_until_next_session` 时，结果会返回 `status: waiting` 和调度器上下文。较长的 paper run 动作返回 `status: queued`，最终结果写入 `GET /api/mvp/paper-trading/runs`。

Run a Strategy Lab backtest:

运行策略实验室回测：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/mvp/strategy-lab/backtests `
  -ContentType "application/json" `
  -Body '{"strategy_id":"deterministic_watchlist_v1","parameters":{}}'
```

## Safety Boundary / 安全边界

VelaQuant is currently a research and paper-trading system. It does not claim live profitability. Before any live-small deployment, the paper system must collect enough real-market samples to prove:

VelaQuant 当前仍是研究与模拟交易系统，不声明已经具备实盘盈利能力。在进入 live-small 前，模拟盘必须积累足够真实市场样本，证明：

- stable positive expectancy;
- sufficient filled-order and closed-trade sample size;
- event-ledger replayability;
- risk-limit discipline;
- strategy evaluation and review continuity.

中文检查项：

- 稳定正期望；
- 足够的成交订单和闭环交易样本；
- 事件账本可回放；
- 风控限制执行稳定；
- 策略评价和复盘连续。

No part of this repository should be treated as investment advice.

本仓库内容不构成投资建议。

## Repository Layout / 目录结构

```text
apps/api/      FastAPI backend, Trading Core, paper trading, strategy lab
apps/web/      Next.js frontend
docs/          design notes, development plans, and architecture records
docker-compose.yml
```

中文说明：

- `apps/api/`：FastAPI 后端、Trading Core、模拟交易、策略实验室。
- `apps/web/`：Next.js 前端。
- `docs/`：设计说明、开发计划和架构记录。
- `docker-compose.yml`：本地完整运行环境。

## Current Brand / 当前品牌

The formal product name is **VelaQuant**.

正式产品名称为 **VelaQuant**。

Recommended GitHub About description:

建议 GitHub About 描述：

```text
VelaQuant: event-driven US equities trading infrastructure with its own Trading Core.
```

Recommended GitHub topics:

建议 GitHub Topics：

```text
event-driven
trading-core
quant-research
paper-trading
us-equities
```

Historical planning documents may still mention earlier working names or local Windows paths. Runtime package metadata and user-facing product surfaces should use VelaQuant going forward.

历史计划文档中可能仍保留早期工作名或本机 Windows 路径。后续运行时包信息和用户可见产品界面统一使用 VelaQuant。
