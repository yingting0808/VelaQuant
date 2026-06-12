# Strategy Lab V2 参数化回测与历史记录设计

## 1. 目标

本阶段把策略实验室从“单次触发内置 LEAN 回测”升级为一个更像研究工作台的闭环：

- 用户可以配置内置策略参数，而不是只能运行固定 AAPL 样例。
- 每次运行都会留下历史记录，便于比较成功、失败和环境未就绪的结果。
- 页面能清楚展示 LEAN / Docker 未就绪时的下一步，而不是让用户猜问题在哪里。
- 继续保持安全边界：只做本地历史回测，不做实盘、不下单、不接券商、不运行用户上传代码。

## 2. 背景

当前系统已经具备：

- FastAPI MVP API。
- Next.js App Router 前端。
- Strategy Lab readiness 检测。
- 一个内置 LEAN `MovingAverageCross` 项目。
- 后端 `lean backtest` runner、结果解析、latest summary。
- 前端 `/strategy-lab` 页面和 `LEAN 回测` 面板。

QuantConnect 官方文档说明，LEAN 项目参数应放在项目 `config.json` 的 `parameters` 字段中，键和值都是字符串；算法中通过 `get_parameter` / `GetParameter` 读取参数。官方写法也支持给 `get_parameter` 提供默认值，使返回值按默认值类型处理。这意味着本阶段应复用 LEAN 参数体系，而不是自研一套策略参数注入机制。

参考：

- https://www.quantconnect.com/docs/v2/lean-cli/optimization/parameters
- https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/parameters

## 3. 范围

### 3.1 本阶段包含

- 给策略目录增加参数定义。
- 后端校验并规范化回测请求参数。
- 每次回测创建运行时 LEAN workspace 副本，并把参数写入副本项目 `config.json`。
- 后端继续用 `lean backtest <project> --output <dir>` 调用成熟 LEAN CLI。
- 保存 latest summary，同时维护历史索引。
- 新增历史 API。
- 前端增加参数表单。
- 前端增加回测历史列表。
- 前端展示环境未就绪的明确行动提示。
- 更新 `MovingAverageCross`，从 LEAN project parameters 读取 symbol、日期、cash、fast/slow period。
- 自动化测试覆盖参数校验、运行时 workspace 副本、历史索引、API、前端交互。

### 3.2 本阶段不包含

- 用户上传或编辑策略代码。
- 自动安装 Docker Desktop、LEAN CLI 或市场数据。
- LEAN 参数优化网格搜索。
- 多任务后台队列。
- 并发运行调度。
- HTML/PDF 报告生成。
- 真实券商、实盘、下单、仓位执行。
- AI 自动生成可执行策略代码。

## 4. 产品行为

### 4.1 参数表单

`/strategy-lab` 的 LEAN 回测面板在策略卡片旁展示参数表单。

默认参数：

- `symbol`: `AAPL`
- `start_date`: `2020-01-01`
- `end_date`: `2021-01-01`
- `cash`: `100000`
- `fast_period`: `20`
- `slow_period`: `50`

表单规则：

- ticker 自动转大写，只允许 1 到 12 位英文字母、数字、点号或连字符。
- 日期必须是 `YYYY-MM-DD`，且 start date 早于 end date。
- cash 必须在 `1000` 到 `1000000000` 之间。
- fast period 必须在 `2` 到 `400` 之间。
- slow period 必须在 `3` 到 `600` 之间。
- fast period 必须小于 slow period。

技术名不强行汉化：`AAPL`、`Daily`、`Sharpe`、`Drawdown`、`LEAN CLI`、`Docker` 保持英文。

### 4.2 运行回测

用户点击“运行回测”后：

1. 前端禁用按钮并展示运行中状态。
2. 后端验证 strategy id 和参数。
3. 后端检查 Strategy Lab readiness。
4. 如果 Docker 或 LEAN CLI 未就绪，后端不复制 workspace、不启动命令，保存 `unavailable` 运行记录。
5. 如果就绪，后端创建 `apps/api/.runtime/strategy-lab/workspaces/<run_id>/`。
6. 后端复制 catalog 中的策略项目到运行时 workspace。
7. 后端把请求参数写入运行时项目 `config.json` 的 `parameters` 字段，所有值以字符串写入，符合 LEAN 项目参数约定。
8. 后端在运行时 workspace 中执行 `lean backtest MovingAverageCross --output <output_dir>`。
9. 后端解析结果 JSON，保存 latest 和 history index。
10. 前端刷新结果和历史列表。

运行时 workspace 副本用于避免修改仓库内的 `lean-workspace/MovingAverageCross/config.json`，也让不同运行记录天然可追溯。

### 4.3 回测历史

页面显示最近最多 10 条历史记录：

- 运行时间。
- strategy name/id。
- symbol。
- 日期范围。
- fast/slow period。
- status。
- 总收益、Sharpe、回撤、交易次数。

历史列表只展示摘要，不展示完整 LEAN JSON。完整输出目录仍只在本机 runtime 下保留。

### 4.4 环境未就绪提示

现有 readiness 面板保留。回测面板中如果最近结果是 `unavailable`，额外展示行动提示：

- Docker CLI 不可用：安装或启动 Docker Desktop，并确认 `docker --version` 可执行。
- Docker engine 不可用：启动 Docker Desktop 后重试。
- LEAN CLI 不可用：安装 QuantConnect LEAN CLI，并确认 `lean --version` 可执行。

系统不会自动安装这些系统级依赖。本阶段只给出明确路径和状态，避免静默改动机器环境。

## 5. 后端设计

### 5.1 策略目录参数定义

`apps/api/lean-workspace/strategies.json` 增加 `parameters` 数组。每个参数包含：

- `name`
- `label`
- `kind`: `ticker`、`date`、`integer`、`number`
- `default`
- `min`
- `max`
- `required`

后端 `StrategyDefinition.public_payload()` 将参数定义暴露给前端，但不暴露本地 `project_path`。

### 5.2 请求模型

`BacktestBody` 从仅有 `strategy_id` 扩展为：

```json
{
  "strategy_id": "moving_average_cross",
  "parameters": {
    "symbol": "AAPL",
    "start_date": "2020-01-01",
    "end_date": "2021-01-01",
    "cash": "100000",
    "fast_period": "20",
    "slow_period": "50"
  }
}
```

参数值进入后端后统一规范化为字符串 map。数值会先校验范围，再以字符串写入 LEAN `config.json`，因为 LEAN CLI 文档要求 project parameters 的 key/value 都是字符串。

### 5.3 运行时 workspace

新增 helper：

- `_runtime_workspace_directory(runtime_root, run_id)`
- `_prepare_runtime_workspace(strategy, run_id, parameters, runtime_root)`
- `_write_project_parameters(config_path, parameters)`

目录结构：

```text
apps/api/.runtime/strategy-lab/
  backtests/<run_id>/
  workspaces/<run_id>/MovingAverageCross/
  latest-backtest.json
  history.json
```

`lean backtest` 的 working directory 从 catalog workspace 改为运行时 workspace。命令仍使用参数数组，不拼 shell 字符串。

### 5.4 结果模型

`BacktestResult` 增加：

- `parameters: dict[str, str]`

新增摘要模型：

- `BacktestHistoryItem`

历史索引从 latest 结果派生，保留最多 50 条，最新在前。索引写入采用临时文件再 replace，避免写一半造成损坏。

### 5.5 API

新增：

- `GET /api/mvp/strategy-lab/backtests/history?limit=10`

返回：

```json
{
  "history": [
    {
      "run_id": "20260613T101500Z-moving_average_cross",
      "strategy_id": "moving_average_cross",
      "status": "success",
      "started_at": "2026-06-13T10:15:00Z",
      "completed_at": "2026-06-13T10:16:15Z",
      "duration_seconds": 75.0,
      "parameters": {
        "symbol": "AAPL",
        "start_date": "2020-01-01",
        "end_date": "2021-01-01",
        "cash": "100000",
        "fast_period": "20",
        "slow_period": "50"
      },
      "statistics": {
        "total_net_profit": "12.34%",
        "compounding_annual_return": "8.10%",
        "sharpe_ratio": "0.72",
        "drawdown": "15.20%",
        "win_rate": "48%",
        "total_trades": "24"
      }
    }
  ]
}
```

现有 endpoints 保持兼容：

- `GET /api/mvp/strategy-lab/strategies`
- `POST /api/mvp/strategy-lab/backtests`
- `GET /api/mvp/strategy-lab/backtests/latest`

旧客户端不传 `parameters` 时，后端使用策略目录默认值。

## 6. 前端设计

### 6.1 Client API

`apps/web/src/lib/client-api.ts` 增加：

- `StrategyParameterDefinitionPayload`
- `BacktestParametersPayload`
- `BacktestHistoryItemPayload`
- `BacktestHistoryPayload`
- `getBacktestHistory(limit?: number)`

`runStrategyBacktest` 接收第二个参数 `parameters`。旧调用保持可用。

### 6.2 回测面板

`StrategyBacktestPanel` 增加三块：

- 策略列表。
- 参数表单。
- 最近结果和历史列表。

表单使用标准 HTML 控件，不引入额外表单库：

- ticker: text input
- start/end date: date input
- cash/fast/slow: number input

本阶段不做复杂可视化图表，先把研究闭环打稳。

### 6.3 状态展示

- 请求中：按钮显示“运行回测中”。
- success：展示核心指标。
- failed / timeout / malformed_result：展示 message 和日志 tail。
- unavailable：展示 message、缺失工具日志和行动提示。
- history 缺失：展示“暂无历史记录”。

## 7. 测试策略

### 7.1 后端

新增或扩展 pytest：

- catalog 暴露参数定义。
- 默认参数可合并进回测请求。
- 无效 ticker 被拒绝。
- start date 晚于 end date 被拒绝。
- fast period 大于或等于 slow period 被拒绝。
- ready run 会复制运行时 workspace，并在副本 config 写入 `parameters`。
- ready run 的 command cwd 指向运行时 workspace。
- unready run 不复制 workspace、不调用 runner，但仍保存 latest/history。
- success 和 failed 都写入 history。
- history 读取按最新在前且支持 limit。
- 损坏的 history json 返回空列表，不让 API 500。

### 7.2 API

- `POST /backtests` 接收参数并返回 `parameters`。
- `POST /backtests` 对无效参数返回 422。
- `GET /backtests/history` 返回历史摘要。
- unknown strategy id 仍返回 404。

### 7.3 前端

Playwright 覆盖：

- Strategy Lab 显示参数表单默认值。
- 修改参数后点击“运行回测”，请求体包含 parameters。
- 回测完成后 history 展示新结果。
- unready response 显示行动提示。

## 8. 验收标准

- 后端测试通过：`python -m pytest -v`。
- 前端 lint 通过：`npm run lint`。
- 前端 build 通过：`npm run build`。
- Playwright 通过：`npx playwright test`。
- Compose 配置通过：`docker compose config`。
- `/strategy-lab` 可配置参数并发起回测。
- 未安装 LEAN CLI 或 Docker engine 未启动时，页面仍显示结构化未就绪状态。
- 仓库内 `apps/api/lean-workspace/MovingAverageCross/config.json` 不会因运行回测被修改。
- 自动化测试不依赖真实 Docker、LEAN CLI 或外部网络。

## 9. 自检

- 没有未完成占位、开放问题或未决选择。
- 范围保持在 Strategy Lab v2，没有引入实盘、券商、队列或策略代码编辑器。
- 参数注入复用 LEAN 官方 project parameters。
- 历史记录只做本地 runtime 摘要，符合当前无数据库架构。
- 旧 API 调用保持兼容。
