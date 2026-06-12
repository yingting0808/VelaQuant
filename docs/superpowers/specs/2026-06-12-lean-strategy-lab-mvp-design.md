# LEAN 策略实验室 MVP 设计

## 1. 目标

本阶段把现有“策略实验室”从环境 readiness 面板推进到一个可验证的本地回测闭环：

- 展示内置 LEAN 示例策略。
- 通过后端触发本地 `lean backtest`。
- 展示回测成功、失败或环境未就绪的结构化结果。
- 在前端显示核心指标、日志摘要和失败原因。

本阶段继续遵守产品安全边界：只做本地历史回测，不做实盘、不下单、不接券商、不接云端交易。

## 2. 背景

当前系统已经具备：

- FastAPI MVP API。
- Next.js App Router 前端。
- `/api/mvp/strategy-lab/status`，可检测 Docker CLI、Docker Compose、Docker engine 和 LEAN CLI。
- `/strategy-lab` 页面，展示 Docker / LEAN readiness。
- OpenBB/yfinance 行情层和 Watchlist 市场快照。

QuantConnect 官方文档说明：

- `lean backtest` 会在 Docker 容器中运行本地回测，并把完整结果保存到项目的 `backtests/20260612T101500Z` 这类时间戳目录。
- LEAN CLI 本地运行依赖 Docker。
- 本地项目通常包含 `config.json` 和 `main.py` 等文件，CLI workspace 通常通过 `lean init` 初始化。
- `lean report` 可以基于 backtest results JSON 生成报告，但本阶段不强制生成 HTML/PDF 报告。

## 3. 范围

### 3.1 本阶段包含

- 一个内置 LEAN Python 策略项目：`MovingAverageCross`。
- 策略目录和 metadata 文件，供后端列出策略。
- 后端策略目录服务。
- 后端回测 runner 抽象，测试使用 fake runner，不调用真实 Docker/LEAN。
- 后端本地 `lean backtest` 执行器。
- 后端结果解析器，从 LEAN output directory 中寻找结果 JSON 并提取可用指标。
- 后端 API：
  - `GET /api/mvp/strategy-lab/strategies`
  - `POST /api/mvp/strategy-lab/backtests`
  - `GET /api/mvp/strategy-lab/backtests/latest`
- 前端 Strategy Lab 页面扩展：
  - readiness 仍保留。
  - 策略列表。
  - 运行回测按钮。
  - 回测状态、指标、日志摘要、失败原因。
- 自动化测试覆盖 ready、unready、success、failure、malformed result。

### 3.2 本阶段不包含

- 实盘交易。
- 券商连接。
- 云端 QuantConnect 回测。
- 用户自定义代码编辑器。
- 策略参数优化。
- 多策略并发队列。
- 长期历史任务数据库。
- 自动下载或购买市场数据。
- 使用 AI 自动生成可执行策略代码。

## 4. 产品行为

### 4.1 策略列表

策略实验室页面显示一个内置策略：

- 名称：`MovingAverageCross`
- 语言：Python
- 标的：`AAPL`
- 数据粒度：Daily
- 说明：用于验证 LEAN 本地回测链路，不构成投资建议。

后端从一个显式 metadata 文件读取策略，避免前端写死策略列表。metadata 中包含：

- `id`
- `name`
- `description`
- `language`
- `asset_class`
- `default_symbol`
- `resolution`
- `project_path`
- `enabled`

### 4.2 运行回测

用户点击“运行回测”后：

1. 前端进入“运行中”状态。
2. 后端检查策略 id 是否在白名单里。
3. 后端检查 Strategy Lab readiness。
4. 如果 Docker 或 LEAN CLI 未就绪，后端不启动命令，直接返回 `unavailable` 结果。
5. 如果就绪，后端用参数数组调用 `lean backtest MovingAverageCross --output apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross`。
6. 后端设置超时时间，默认 180 秒。
7. 后端收集 stdout/stderr tail。
8. 后端解析结果 JSON。
9. 后端保存 latest summary，前端展示结果。

本阶段允许 `POST /backtests` 同步等待命令完成。前端用异步请求展示“运行中”。这比引入后台队列更小、更容易验证，也足够支撑第一个本地回测闭环。

### 4.3 最新结果

页面加载时调用 `GET /api/mvp/strategy-lab/backtests/latest`：

- 如果没有运行记录，显示“尚未运行回测”。
- 如果有记录，显示最近一次策略、状态、指标和日志摘要。

latest summary 存在运行时目录，不提交到 Git。

### 4.4 失败状态

所有失败都必须是结构化结果，而不是让页面空白或 API 500：

- `unavailable`：Docker / LEAN CLI / workspace 未就绪。
- `failed`：LEAN 命令退出码非 0。
- `timeout`：命令超过 180 秒。
- `malformed_result`：命令成功但没有可解析结果 JSON。
- `success`：命令成功且至少解析出一个结果 JSON。

失败结果仍保存为 latest summary，方便用户看到最后一次失败原因。

## 5. 后端架构

### 5.1 文件布局

新增后端服务文件：

- `apps/api/app/services/strategy_catalog.py`
  - 读取和校验策略 metadata。
  - 只返回 enabled 策略。

- `apps/api/app/services/lean_backtest.py`
  - 定义 request/result Pydantic 模型。
  - 定义 runner protocol。
  - 实现 subprocess runner。
  - 实现 results parser。
  - 保存/读取 latest summary。

新增策略文件：

- `apps/api/lean-workspace/MovingAverageCross/main.py`
- `apps/api/lean-workspace/MovingAverageCross/config.json`
- `apps/api/lean-workspace/strategies.json`

新增运行时目录：

- `apps/api/.runtime/strategy-lab/`

该目录写入 `.gitignore`。

### 5.2 LEAN workspace

本阶段提交最小策略项目文件，但不把大量本地数据提交进仓库。

如果机器没有完成 `lean init` 或缺少本地数据，系统应返回可理解的 `unavailable` 或 `failed` 结果。页面要提示用户下一步检查 Docker、LEAN CLI 和本地数据，而不是伪造成功。

### 5.3 命令执行

命令必须用参数数组执行，不拼 shell 字符串：

```text
lean backtest MovingAverageCross --output D:\Documents\AI美股\apps\api\.runtime\strategy-lab\backtests\20260612T101500Z-moving_average_cross
```

执行约束：

- working directory 固定为 `apps/api/lean-workspace`。
- strategy id 必须来自 catalog。
- output directory 固定在 `apps/api/.runtime/strategy-lab/backtests/<run_id>`。
- timeout 固定 180 秒。
- stdout/stderr 只保留 tail，避免大日志撑爆响应。

### 5.4 结果解析

解析器从 output directory 中递归寻找 `.json` 文件，优先选择看起来像 backtest result 的 JSON。解析时尽量兼容字段差异：

- `statistics`
- `charts`
- `orders`
- `runtimeStatistics`

MVP 指标字段：

- `total_net_profit`
- `compounding_annual_return`
- `sharpe_ratio`
- `drawdown`
- `win_rate`
- `total_trades`

如果某个字段不存在，返回 `null`，不要报错。

Equity 曲线先做轻量摘要：

- 如果能从 charts 中找到 equity / strategy equity 序列，返回最多 100 个点。
- 如果找不到，返回空数组。

## 6. API 设计

### 6.1 `GET /api/mvp/strategy-lab/strategies`

返回：

```json
{
  "strategies": [
    {
      "id": "moving_average_cross",
      "name": "MovingAverageCross",
      "description": "AAPL daily moving average crossover sample for local LEAN validation.",
      "language": "Python",
      "asset_class": "US Equity",
      "default_symbol": "AAPL",
      "resolution": "Daily",
      "enabled": true
    }
  ]
}
```

### 6.2 `POST /api/mvp/strategy-lab/backtests`

Request:

```json
{
  "strategy_id": "moving_average_cross"
}
```

Response:

```json
{
  "run_id": "20260612T101500Z-moving_average_cross",
  "strategy_id": "moving_average_cross",
  "status": "success",
  "started_at": "2026-06-12T10:15:00Z",
  "completed_at": "2026-06-12T10:16:15Z",
  "duration_seconds": 75.0,
  "message": "Backtest completed.",
  "statistics": {
    "total_net_profit": "12.34%",
    "compounding_annual_return": "8.10%",
    "sharpe_ratio": "0.72",
    "drawdown": "15.20%",
    "win_rate": "48%",
    "total_trades": "24"
  },
  "equity": [],
  "logs": ["TRACE:: Backtest completed"],
  "output_directory": "apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross"
}
```

### 6.3 `GET /api/mvp/strategy-lab/backtests/latest`

如果没有记录：

```json
{
  "latest": null
}
```

如果有记录：

```json
{
  "latest": {
    "run_id": "20260612T101500Z-moving_average_cross",
    "strategy_id": "moving_average_cross",
    "status": "success"
  }
}
```

## 7. 前端设计

### 7.1 Strategy Lab 页面

页面保留现有 readiness panel，并新增：

- 策略列表 panel。
- 回测结果 panel。

按钮行为：

- Docker / LEAN CLI 未就绪时，按钮仍可显示，但点击后返回结构化 unavailable；前端展示失败原因。
- 正在运行时按钮 disabled，显示“运行中”。
- 完成后刷新 latest result。

### 7.2 视觉风格

沿用当前产品风格：

- 信息密度偏工具型。
- 不做营销 hero。
- 使用现有 `data-panel`、`module-row`、`status-pill`、`state-ok`、`state-warn`。
- 指标使用紧凑 grid。
- 日志使用等宽字体、固定高度滚动区域。

### 7.3 文案

需要汉化的业务文案使用中文：

- “策略实验室”
- “运行回测”
- “最近一次回测”
- “环境未就绪”
- “LEAN 返回失败”

不强行汉化的技术标识保持英文：

- Docker
- Docker Compose
- LEAN CLI
- QuantConnect
- MovingAverageCross
- AAPL
- Sharpe
- Drawdown

## 8. 安全和边界

- 不接受用户上传的策略代码。
- 不允许用户输入任意命令。
- 只运行 catalog 中 enabled 的策略。
- 不暴露完整本地绝对路径给前端；API 可返回相对路径或简化路径。
- 不暴露完整 stack trace。
- 不把 stdout/stderr 完整无限返回。
- 不记录 API key、cookie、token。
- 不触发 live trading 相关命令。
- 不自动安装 Docker、LEAN CLI 或下载市场数据。

## 9. 测试策略

### 9.1 后端单元测试

- Catalog 能读取内置策略。
- 禁用策略不会出现在 API。
- 无效 strategy id 返回 404 或结构化错误。
- Fake runner success 生成 `success` summary。
- Fake runner nonzero exit 生成 `failed` summary。
- Fake runner timeout 生成 `timeout` summary。
- 缺少 Docker / LEAN readiness 时生成 `unavailable` summary。
- Malformed JSON 生成 `malformed_result` summary。
- latest summary 可保存和读取。

### 9.2 API 测试

- `GET /strategies` 返回内置策略。
- `POST /backtests` 返回结构化结果。
- `GET /backtests/latest` 初始返回 null。
- 运行后 latest 返回最近一次结果。

### 9.3 前端测试

- Strategy Lab 页面仍显示 readiness。
- Strategy Lab 页面显示 `MovingAverageCross`。
- 点击“运行回测”后显示运行中，再显示 fake success 指标。
- mocked failure response 显示失败原因。
- latest result 在页面加载时显示。

### 9.4 手动验证

如果本机 Docker 和 LEAN CLI 可用：

- 打开 `http://127.0.0.1:3000/strategy-lab`。
- 点击“运行回测”。
- 看到 success 或清晰的 LEAN 数据缺失错误。

如果本机环境未就绪：

- 页面必须显示清楚原因。
- API 不能 500。

## 10. 验收标准

- `python -m pytest -v` 通过。
- `npm run lint` 通过。
- `npm run build` 通过。
- `npx playwright test` 通过。
- `docker compose config` 通过。
- `/strategy-lab` 可以列出策略并触发回测请求。
- 未安装 Docker 或 LEAN CLI 时，页面显示结构化未就绪状态。
- 自动化测试不依赖真实 Docker、LEAN CLI 或外部网络。
- 没有实盘、下单、券商连接入口。

## 11. 参考

- QuantConnect LEAN backtest API reference: https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-backtest
- QuantConnect LEAN CLI installation: https://www.quantconnect.com/docs/v2/lean-cli/installation/installing-lean-cli
- QuantConnect LEAN project structure: https://www.quantconnect.com/docs/v2/lean-cli/projects/structure
- QuantConnect LEAN reports: https://www.quantconnect.com/docs/v2/lean-cli/reports
