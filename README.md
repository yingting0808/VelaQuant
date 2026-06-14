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
  -> PostgreSQL + Redis
```

Core rules:

核心规则：

- `StrategyRegistry` is the strategy entry point.
- `TradeIntent` must pass through risk before execution.
- `ExecutionEngine` records order state transitions.
- Production events are persisted through the event ledger.
- AI is for research, explanation, and event structuring, not direct order decisions.
- LEAN and vectorbt are research/backtest tools, not live execution paths.

中文说明：

- `StrategyRegistry` 是策略进入系统的入口。
- `TradeIntent` 必须先经过风控，才能进入执行。
- `ExecutionEngine` 记录订单状态机变化。
- 生产事件必须写入事件账本。
- AI 只用于研究、解释和事件结构化，不直接生成交易指令。
- LEAN 和 vectorbt 只用于研究/回测，不进入实盘执行路径。

## Tech Stack / 技术栈

Backend / 后端：

- FastAPI
- Pydantic
- SQLModel
- PostgreSQL
- Redis Streams
- APScheduler
- vectorbt
- QuantConnect LEAN CLI integration for research workflows

Frontend / 前端：

- Next.js
- React
- TypeScript
- Playwright tests

Runtime / 运行环境：

- Docker Compose
- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3000`

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
