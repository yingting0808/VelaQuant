# VelaQuant

VelaQuant is a local-first US equities research and paper-trading system for building a verifiable alpha loop before any small-capital live deployment.

VelaQuant 是一个本地优先的美股投研与模拟交易系统，目标是在进入小资金实盘前，先建立可验证的 Alpha 闭环。

This project is not a simple trading bot. It is an event-driven trading-system foundation that separates market data, strategy decisions, risk control, execution, paper accounting, backtesting, and AI-assisted research.

本项目不是简单的交易机器人，而是事件驱动的交易系统底座。系统将市场数据、策略决策、风控、执行、模拟盘记账、回测和 AI 辅助研究拆分为清晰边界。

## Current System Role / 当前系统定位

VelaQuant currently focuses on controlled paper trading:

VelaQuant 当前重点是受控模拟交易：

- Generate daily strategy candidates from the active watchlist strategy.
- Explain candidate rationale with structured evidence.
- Route simulated orders through the Trading Core risk and execution chain.
- Persist event-ledger traces for audit and replay.
- Record paper PnL, reviews, and strategy diagnostics.
- Run historical research backtests through the Strategy Lab.
- Keep AI out of the production execution path.

中文对应能力：

- 从当前活跃自选股策略中生成每日候选。
- 用结构化证据解释候选原因。
- 将模拟订单统一送入 Trading Core 的风控与执行链路。
- 持久化事件账本，支持审计和回放。
- 记录模拟盘盈亏、复盘和策略诊断。
- 通过策略实验室运行历史回测。
- 保持 AI 与生产执行路径隔离。

The system is designed to prove paper-trading expectancy and execution discipline before moving toward live-small trading.

系统设计目标是在进入 live-small 前，先证明模拟盘净期望、执行纪律和风控链路稳定。

## Current Verified Progress / 当前已验证进度

Runtime-verified on Docker Compose as of 2026-06-14:

截至 2026-06-14，已在 Docker Compose 运行态验证：

- API, web, PostgreSQL, and Redis run together through Docker Compose.
- `POST /api/mvp/paper-trading/action-plan/execute-primary` executes quick safe actions synchronously and queues long paper-run actions so the browser request does not block.
- `collect_post_limit_sample` uses the normal paper trading loop with a controlled `force_new_sample` flag, so a post-limit sample can create a new run even when the same trading day already has a completed run.
- Candidate-only event chains (`MarketEvent -> StrategyInput -> TradeIntent`) are treated as replayable evidence; repair is reserved for missing ledgers or broken risk/order chains.
- Latest verified paper run: `56ecff01-3896-4fe8-a608-5e7a84096339`, trading day `2026-06-12`, status `completed`, 7 candidates, 21 replayable core events.
- Latest operations status: `ready`, no runtime blockers, event ledger ready.
- Latest Alpha gate state: 5/9 gates passed; still collecting review days, consecutive positive expectancy days, filled-order sample, and closed-trade sample.
- Current recommended action after the verified run: apply the next paper-only risk-limit recommendation (`max_daily_orders 9 -> 10`); live limits remain unchanged.

中文对应事实：

- API、Web、PostgreSQL、Redis 已通过 Docker Compose 一起运行。
- `POST /api/mvp/paper-trading/action-plan/execute-primary` 会同步执行快速安全动作，并将较长的 paper run 动作排入后台，避免浏览器请求阻塞。
- `collect_post_limit_sample` 仍走同一条 paper trading loop，只通过受控的 `force_new_sample` 标记生成限额更新后的新样本。
- 仅包含候选和 `TradeIntent` 的事件链会被视为可回放证据；repair 只用于缺失账本或损坏的风控/订单链。
- 最新已验证 paper run：`56ecff01-3896-4fe8-a608-5e7a84096339`，交易日 `2026-06-12`，状态 `completed`，7 个候选，21 条可回放 core events。
- 最新运行健康状态：`ready`，无运行阻断，事件账本可回放。
- 最新 Alpha 门禁：5/9 通过；仍需继续收集复盘天数、连续正期望天数、成交订单样本和闭环交易样本。
- 当前推荐动作：应用下一次仅限 Paper 的风险限额建议（`max_daily_orders 9 -> 10`）；live 限额不变。

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
- LangGraph orchestrates the deterministic AI research workflow, not order execution.
- OpenBB provides market-data/research access when available, but it does not bypass the data-provider abstraction or execution path.
- LEAN and vectorbt are research/backtest tools, not live execution paths.

中文说明：

- `StrategyRegistry` 是策略进入系统的入口。
- `TradeIntent` 必须先经过风控，才能进入执行。
- `ExecutionEngine` 记录订单状态机变化。
- 生产事件必须写入事件账本。
- AI 只用于研究、解释和事件结构化，不直接生成交易指令。
- LangGraph 用于编排确定性的 AI 投研 workflow，不用于订单执行。
- OpenBB 在可用时提供行情和研究数据能力，但不能绕过数据源抽象层或交易执行路径。
- LEAN 和 vectorbt 只用于研究/回测，不进入实盘执行路径。

## Tech Stack / 技术栈

Backend / 后端：

- FastAPI
- Pydantic
- SQLModel
- PostgreSQL
- Redis Streams
- APScheduler
- LangGraph
- OpenBB
- vectorbt
- QuantConnect LEAN CLI integration for research workflows
- pandas / numpy
- pandas-market-calendars
- pytest

Backend support libraries / 后端支撑库：

- `psycopg`: PostgreSQL driver.
- `httpx`: HTTP client used by data and provider integrations.
- `openpyxl`: spreadsheet import support.
- `pydantic-settings`: environment-driven runtime configuration.

中文说明：

- `psycopg`：PostgreSQL 驱动。
- `httpx`：数据源和 provider 集成使用的 HTTP 客户端。
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

VelaQuant uses LangGraph in `apps/api/app/ai/workflow.py` to run the research assistant workflow behind `POST /api/mvp/research`.

VelaQuant 在 `apps/api/app/ai/workflow.py` 中使用 LangGraph，支撑 `POST /api/mvp/research` 背后的投研助手 workflow。

Current workflow behavior:

当前 workflow 行为：

- Input: ticker, user question, and structured evidence items.
- Output: summary, bull case, bear case, watch items, and a trade-plan draft.
- If evidence is missing, the workflow returns an `insufficient_evidence` result.
- The trade-plan draft is explicitly not an executable order.

中文说明：

- 输入：ticker、用户问题和结构化证据项。
- 输出：摘要、多头观点、空头风险、观察项和交易计划草稿。
- 如果证据不足，workflow 返回 `insufficient_evidence`。
- 交易计划草稿不是可执行订单。

Current boundary:

当前边界：

- LangGraph is used for deterministic research workflow orchestration.
- It does not generate `TradeIntent`.
- It does not call `ExecutionEngine`.
- It does not bypass `StrategyRegistry` or `RiskEngine`.

中文说明：

- LangGraph 当前用于确定性投研 workflow 编排。
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
GET  /api/mvp/strategy-lab/alpha-gates
GET  /api/mvp/strategy-lab/evaluation
POST /api/mvp/strategy-lab/backtests
```

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

Quick actions return `status: completed`. Long paper-run actions return `status: queued` and write their final outcome to `GET /api/mvp/paper-trading/runs`.

快速动作返回 `status: completed`。较长的 paper run 动作返回 `status: queued`，最终结果写入 `GET /api/mvp/paper-trading/runs`。

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

Historical planning documents may still mention earlier working names or local Windows paths. Runtime package metadata and user-facing product surfaces should use VelaQuant going forward.

历史计划文档中可能仍保留早期工作名或本机 Windows 路径。后续运行时包信息和用户可见产品界面统一使用 VelaQuant。
