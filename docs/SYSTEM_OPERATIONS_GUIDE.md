# VelaQuant 系统操作说明

最后核对日期：2026-06-15
适用系统：本仓库当前 Docker Compose 运行态，Web `http://127.0.0.1:3000`，API `http://127.0.0.1:8000`

## 1. 先读结论

VelaQuant 是一套本地优先的美股投研、回测、模拟盘和交易内核系统。它不是简单的聊天机器人，也不是 LEAN、OpenBB、LangGraph 或前端页面的套壳。

系统当前定位：

- 已有自研事件驱动 Trading Core。
- 已有模拟盘日循环、候选生成、风控、执行状态机、事件账本、盈亏记录、策略复盘和 Alpha 门禁。
- 已接入 OpenBB 数据访问、SEC EDGAR、LEAN 回测、vectorbt 研究回测、LangGraph 投研 workflow、OpenAI-compatible LLM 投研解释；MockProvider 仅保留给显式开发/测试模式，不参与默认 hybrid 模拟盘证据链。
- 当前 live 或 broker execution 仍关闭，系统处于 controlled paper trading 阶段。
- AI 助手只做投研解释、风险梳理、情景拆解和交易计划草稿，不生成可执行订单，不调用 ExecutionEngine，不绕过 RiskEngine。

当前运行态重点事实：

- `data_sources/status` 默认 hybrid 显示 SEC EDGAR、OpenBB；MockProvider 不在默认运行态暴露。
- `ai/status` 显示 LangGraph 可用，OpenAI-compatible research LLM 已配置且可用，当前模型为 `mimo-v2.5-pro`。
- `strategy-lab/status` 显示 Docker、LEAN、LEAN Docker image、vectorbt 可用。
- `system-readiness` 显示系统可进行 controlled daily runs，生命周期阶段为 `paper`，live/broker execution disabled。
- 最新 Daily Report 显示仍需继续收集 Alpha 样本，阻断项包括复盘天数、连续正期望、成交订单样本、闭环交易样本。

## 2. 启动与访问

在仓库根目录运行：

```powershell
docker compose up -d
```

常用地址：

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:3000` | Web 操作台 |
| `http://127.0.0.1:3000/paper-trading` | 模拟盘工作台 |
| `http://127.0.0.1:3000/strategy-lab` | 策略实验室 |
| `http://127.0.0.1:3000/settings` | 数据源、AI、运行配置 |
| `http://127.0.0.1:8000/health` | API 健康检查 |
| `http://127.0.0.1:8000/api/mvp/ai/status` | AI 与 LLM 状态 |
| `http://127.0.0.1:8000/api/mvp/data-sources/status` | 数据源状态 |

常用检查命令：

```powershell
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:3000/paper-trading -UseBasicParsing
```

如果刚启动后 API 或 Web 短暂不可用，先看日志：

```powershell
docker compose logs --tail=80 api
docker compose logs --tail=80 web
```

## 3. 系统结构

整体结构：

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
  -> Paper Trading Account / Reviews
  -> Strategy Lab / Backtests / Evaluation
  -> AI Research Workflow
  -> PostgreSQL + Redis
```

核心代码路径：

| 路径 | 作用 |
| --- | --- |
| `apps/api/app/trading_core/` | 自研 Trading Core |
| `apps/api/app/services/paper_trading.py` | 模拟盘日循环、候选、订单、持仓、复盘 |
| `apps/api/app/services/strategy_registry.py` | 策略注册、策略入口、策略可执行状态 |
| `apps/api/app/services/strategy_runtime.py` | 策略运行态、策略竞争和执行绑定 |
| `apps/api/app/services/strategy_lifecycle.py` | 策略生命周期判断 |
| `apps/api/app/services/strategy_evaluation.py` | 策略评价 |
| `apps/api/app/services/strategy_attribution.py` | 策略归因 |
| `apps/api/app/services/alpha_validation.py` | Alpha 验证 |
| `apps/api/app/services/paper_action_plan.py` | 模拟盘行动计划 |
| `apps/api/app/ai/` | LangGraph workflow、LLM client、AI schema |
| `apps/web/src/components/` | Web 页面组件 |

## 4. Trading Core 运行逻辑

Trading Core 是 VelaQuant 自研的运行时交易内核。外部工具不能替代它。

标准执行链路：

```text
StrategyRegistry
  -> StrategyExecutionBinding
  -> MarketEvent
  -> StrategyInput
  -> TradeIntent
  -> RiskDecision
  -> ExecutionEngine
  -> OrderState
  -> EventLedger
```

含义：

1. `StrategyRegistry` 决定哪些策略可进入运行态。
2. 策略产生 `TradeIntent`，表示想买入或卖出某个标的。
3. `RiskEngine` 强制检查交易意图，拒绝超限或不合规动作。
4. `ExecutionEngine` 只处理通过风控的订单，并记录订单状态机。
5. `EventLedger` 将关键事件落库，便于审计、回放、归因和复盘。

当前系统必须遵守：

- 策略必须经过 Registry 控制。
- AI 不生成 `TradeIntent`。
- LEAN/vectorbt 只做研究和回测，不进入模拟盘执行主路径。
- OpenBB 只做数据访问，不做券商、风控或执行。
- live/broker execution 当前关闭。

## 5. Web 页面功能

### 5.1 总览

入口：`/`

主要用途：

- 查看主组合市值、持仓权重、事件预警。
- 打开 AI 助手进行当前页面解释、组合风险识别、情景拆解、交易计划草稿。

重点名词：

- 组合市值：当前持仓按市场价格估算后的总价值。
- 权重：单个持仓在组合中的占比。
- 事件预警：来自 SEC、数据源或系统规则的待关注事件。

### 5.2 自选股

入口：`/watchlist`

主要用途：

- 维护关注标的和投资假设。
- 查看指定 ticker 的市场快照。
- 为候选生成和研究工作提供输入。

重点名词：

- Watchlist：自选股池，表示系统需要持续观察的标的集合。
- Thesis：投资假设，说明为什么关注这个 ticker。
- Market Snapshot：行情、基本面、历史价格和数据源状态的组合视图。

### 5.3 组合

入口：`/portfolio`

主要用途：

- 维护组合持仓。
- 新增、更新、删除持仓信息。
- 作为风险、权重和 AI 风险解释的上下文。

重点名词：

- Position：持仓记录，包括 ticker、数量、成本或市值。
- Portfolio：组合账本，代表一组持仓。
- Exposure：风险暴露，表示组合对某个 ticker、行业或主题的敏感度。

### 5.4 模拟盘

入口：`/paper-trading`

这是当前系统最重要的运行页面。

主要用途：

- 查看每日模拟盘报告。
- 运行或观察 daily paper trading loop。
- 查看候选池、模拟订单、模拟持仓、事件账本、行动计划、风险配置、策略复盘。
- 记录候选 -> 订单 -> 盈亏 -> 复盘 -> Alpha gate 的闭环证据。

关键区域：

| 区域 | 作用 |
| --- | --- |
| 今日简报 | 显示当前交易日运行状态、账户权益、现金、PnL、Alpha blocker |
| 行动计划 | 给出下一步推荐动作，例如等待下一交易日、记录快照、复盘评分反向 |
| 候选池 | 展示每日策略候选、来源策略、排名分数、是否可下单 |
| 模拟订单 | 显示已提交、成交、拒绝的 paper orders |
| 模拟持仓 | 显示当前 paper positions |
| 事件账本 | 展示事件链、候选解释、订单状态、可追溯性 |
| 风险配置 | 展示模拟盘风控限额 |
| 策略复盘记录 | 展示人工或系统记录的策略 review 事件 |

当前 Daily Report 关键字段：

- `health_status=ready`：日循环运行健康。
- `recommended_action=hold_until_next_session`：当前日样本已处理，等待下一次有效交易日采样。
- `alpha_ready=false`：尚未达到 Alpha 可用标准。
- `alpha_blockers`：仍需补足的验证门禁。
- `open_alpha_gates`：每个未通过门禁的当前值、目标值和剩余缺口。
- `exit_watchlist`：已有 paper position 是否接近止盈/止损，是否能贡献闭环交易样本。

### 5.5 策略实验室

入口：`/strategy-lab`

主要用途：

- 检查 Docker、LEAN、vectorbt、回测环境。
- 运行策略回测。
- 查看 Strategy Registry、Strategy Competition、Lifecycle、Alpha Validation、Shadow Review 等状态。
- 判断策略是否有足够 evidence 进入下一阶段。

当前已接入策略：

- `deterministic_watchlist_v1`
- `moving_average_cross`

关键能力：

- LEAN 回测：用于研究和历史验证。
- vectorbt 回测：用于快速研究 replay。
- Strategy Registry：决定哪些策略进入 paper runtime。
- Strategy Competition：比较策略运行证据和排序分数。
- Lifecycle：显示策略处于 paper、shadow、live-small、live、killed 中哪个阶段。
- Alpha Gates：展示策略是否通过样本、期望、回撤、归因等门禁。

注意：

- 策略实验室的回测结果不能自动变成实盘订单。
- 回测通过只代表有研究证据，还需要 paper runtime 样本验证。
- live-small 需要人工 review，当前 broker execution 仍关闭。

### 5.6 研究笔记

入口：`/notes`

主要用途：

- 保存 AI 研究结果。
- 手动记录 ticker 研究结论。
- 保留投研过程证据。

AI 助手的研究结果可以保存为笔记。保存动作调用后端 `/api/mvp/research/notes`，不是纯前端本地保存。

### 5.7 数据导入

入口：`/imports`

主要用途：

- 导入持仓 CSV。
- 检查行级错误。
- 将外部持仓数据进入 VelaQuant 组合视图。

### 5.8 设置

入口：`/settings`

主要用途：

- 查看数据源状态。
- 查看 AI / LangGraph / LLM 状态。
- 调整运行配置。
- 保存或清除 OpenAI-compatible API key。

当前可见配置包括：

- 数据模式。
- SEC EDGAR User-Agent。
- LEAN 回测超时。
- OpenAI Research LLM 开关、模型、Base URL、超时、API key。

安全边界：

- API key 保存后只供后端使用。
- API 响应不会回显密钥明文。
- AI 设置不会改变 AI 不能下单的系统规则。

## 6. AI 助手能做什么

AI 助手位于页面右下角，可收起和展开。

默认状态：

- 默认收起，不长期占用右侧页面空间。
- 点击“展开 AI 助手”后打开右侧抽屉。
- 展开后的动作会调用真实 `/api/mvp/research` 接口。

当前可用动作：

| 动作 | 能做什么 |
| --- | --- |
| 解释当前页面 | 根据当前默认研究上下文解释页面含义和关注点 |
| 识别组合风险 | 从持仓、事件、证据中梳理组合风险 |
| 生成多/中/空情景 | 生成 bull/base/bear 研究视角 |
| 起草交易计划 | 生成研究型交易计划草稿，包括入场条件、失效条件、风控提示 |
| 保存为笔记 | 将当前 AI 研究结果保存到研究笔记 |

AI 助手不会做：

- 不会生成可执行订单。
- 不会直接改变持仓。
- 不会绕过 Strategy Registry。
- 不会绕过 RiskEngine。
- 不会调用 ExecutionEngine。
- 不会影响 live/broker execution。

AI 结果状态：

- `LLM 已生成`：OpenAI-compatible LLM 调用成功。
- `本地规则`：LLM 不可用或后端降级到确定性本地研究逻辑。
- `证据不足`：当前 ticker 证据不足，系统拒绝过度解释。
- `离线兜底`：API 不可用或请求失败时的前端 fallback。

当前运行态：

- LangGraph 可用，职责是 research workflow orchestration。
- OpenAI-compatible research LLM 已配置且可用。
- `ai_generates_trade_intent=false`
- `ai_influences_risk=false`
- `ai_calls_execution=false`

## 7. 每日模拟盘运行逻辑

每日模拟盘目标不是“随便模拟交易”，而是稳定产生可审计样本：

```text
调度器触发
  -> 检查美股交易日
  -> 拉取数据源和策略上下文
  -> Strategy Registry 选择可运行策略
  -> 生成候选
  -> 写入 trade_explanation 事件
  -> 生成 TradeIntent
  -> RiskEngine 审批
  -> ExecutionEngine 生成/更新模拟订单
  -> 更新 paper account 和 positions
  -> 记录 EventLedger
  -> 生成 Daily Report
  -> 更新 Alpha gates 和 Action Plan
```

当前 Scheduler：

- 运行中。
- 下一次有效运行时间：`2026-06-16T06:30:00+08:00`。
- 下一次有效交易日：`2026-06-15`。
- 当前系统建议：等待下一次有效 paper run。

模拟盘不会自动实盘化。即使 Alpha gate 通过，也仍需要生命周期、shadow、live-small manual review 和 broker execution 配置。

## 8. Alpha 验证与策略进化逻辑

Alpha 验证用于回答：策略是否有足够证据进入下一阶段。

当前尚未 ready 的门禁：

| 门禁 | 当前值 | 要求 | 还差 |
| --- | ---: | ---: | ---: |
| 复盘天数 | 1 天 | 5 天 | 4 天 |
| 连续正期望 | 1 天 | 5 天 | 4 天 |
| 成交订单 | 10 笔 | 30 笔 | 20 笔 |
| 闭环交易 | 6 笔 | 10 笔 | 4 笔 |

关键逻辑：

- `filled_order_sample`：成交订单样本量。
- `closed_trade_sample`：已闭环交易样本量。
- `expectancy`：每笔交易的平均期望收益。
- `score_pnl_inversion_review`：候选评分方向和实际盈亏相反时，需要复盘隔离。
- `strategy_review`：记录复盘动作，避免同一问题反复成为首要行动。

当前系统已经可以把候选 `candidate_id` 贯穿到订单和后续 PnL 归因，因此复盘不只看 ticker，还能追到“哪一个候选理由导致了这笔交易”。

## 9. 回测逻辑

VelaQuant 当前有两类回测能力：

| 回测工具 | 用途 | 运行边界 |
| --- | --- | --- |
| LEAN | 更接近专业量化研究环境的策略历史回测 | 只用于研究/回测，不进入执行主路径 |
| vectorbt | 快速研究 replay 和策略历史验证 | 只用于研究/回测，不替代 Trading Core |

当前 LEAN 环境已就绪：

- Docker CLI 可用。
- Docker Compose 可用。
- Docker engine 可用。
- `quantconnect/lean:latest` 已缓存。
- LEAN CLI 可用。
- vectorbt 可用。

重要边界：

- 回测收益不是实盘收益承诺。
- 回测通过不能直接晋级 live。
- 回测只是 Strategy Registry 和 Strategy Competition 的证据之一。
- 策略必须在 paper runtime 中继续收集真实运行样本。

## 10. 数据源逻辑

当前数据源状态：

| 数据源 | 当前状态 | 作用 |
| --- | --- | --- |
| Mock | 开发/测试模式 | 本地确定性数据，不进入默认 hybrid 模拟盘证据链 |
| SEC EDGAR | 可用 | 获取 SEC filings 和公司事件证据 |
| OpenBB | 可用 | 通过 yfinance 等能力获取 quote、history、fundamentals |

数据源边界：

- 策略不能在内部随意直接调用外部 API。
- 数据必须通过 provider abstraction 进入系统。
- OpenBB 失败时，系统会返回结构化不可用状态，避免页面 500；默认 hybrid 不回落到 Mock 市场值。
- OpenBB 不负责下单，不负责风控，不负责执行。

## 11. 风控与执行逻辑

RiskEngine 是强制门禁。

典型风控包括：

- 单笔订单名义金额限制。
- 持仓权重限制。
- 每日订单数量限制。
- 现金约束。
- 风险降低型卖出和新增买入的区别处理。

ExecutionEngine 负责订单状态机。

常见订单状态：

- `new`：新订单。
- `validated`：基础校验通过。
- `risk_approved`：风控通过。
- `sent`：已送入模拟执行。
- `filled`：模拟成交。
- `rejected`：被风控或执行拒绝。

当前执行仅限 paper trading。live/broker execution 当前关闭。

## 12. 事件账本与审计

EventLedger 是系统的审计记录。

主要事件类型：

- `market_event`
- `strategy_input`
- `trade_intent`
- `risk_decision`
- `order_state`
- `trade_explanation`
- `strategy_review`
- `scheduler_decision`

每条事件通常包含：

- `event_id`
- `correlation_id`
- `causation_id`
- `event_type`
- `payload_json`
- 时间戳

含义：

- `correlation_id`：把同一次链路里的事件串起来。
- `causation_id`：说明当前事件由哪个前置事件导致。
- `payload_json`：结构化业务内容。

事件账本用于：

- 复盘交易链路。
- 查明订单为什么产生。
- 查明订单为什么被拒绝。
- 把候选理由和后续 PnL 关联起来。
- 支撑 Alpha validation 和 strategy attribution。

当前可用查询入口：

| 入口 | 用途 |
| --- | --- |
| `GET /api/mvp/paper-trading/event-ledger` | 查看最近一次可回放运行的事件账本、topic 计数和链路完整性 |
| `GET /api/mvp/paper-trading/market-events?ticker=INTC` | 查看指定 ticker 的市场事件，以及后续 TradeIntent、RiskDecision、OrderState、解释和证据 |
| Web UI：`模拟盘 -> 事件与AI -> 市场事件中心` | 面向运行人员查看 SPCX、INTC 等标的的事件、原因、逐 topic payload 和追溯链 |

## 13. 策略生命周期

目标生命周期：

```text
paper -> shadow -> live-small -> live -> killed
```

当前运行态：

- 当前阶段：`paper`。
- `alpha_ready=false`。
- `shadow_can_record=false`。
- `live_small_review_ready=false`。
- `live_or_broker_execution_enabled=false`。

含义：

- `paper`：只做模拟交易和样本验证。
- `shadow`：策略观察，不实际下单。
- `live-small`：小资金实盘试运行，需要人工审批。
- `live`：正式实盘阶段。
- `killed`：策略被淘汰或禁用。

当前系统没有进入 live-small，也没有开启 broker execution。

## 14. 操作流程建议

日常使用顺序：

1. 打开 `/settings`，确认数据源和 AI 状态。
2. 打开 `/strategy-lab`，确认 Docker、LEAN、vectorbt 和策略状态。
3. 打开 `/paper-trading`，查看 Daily Report。
4. 看 `recommended_action`。
5. 如果是 `hold_until_next_session`，等待下一次有效交易日调度。
6. 如果出现 review action，先看策略复盘记录和事件账本，再执行首要动作。
7. 查看候选池和事件账本，确认候选来源、排名分数、策略 ID、candidate ID。
8. 观察 Alpha gates 缺口，不要在样本不足时进入实盘。

遇到问题时：

- 页面打不开：检查 `docker compose ps` 和 web logs。
- API 不通：检查 `/health` 和 api logs。
- AI 不输出 LLM：检查 `/settings` 的 API key、base URL、模型和 `/api/mvp/ai/status`。
- 回测不可用：检查 `/strategy-lab/status` 的 Docker、LEAN、vectorbt 状态。
- 模拟盘没有新动作：检查是否非美股交易日，或 `recommended_action` 是否为等待下一 session。
- 事件链异常：查看 `/paper-trading` 的事件账本和 repair ledger 动作。

## 15. 专业名词解释

| 名词 | 解释 |
| --- | --- |
| Trading Core | VelaQuant 自研交易内核，负责策略输入、风控、执行状态机和事件账本 |
| Event-driven | 事件驱动架构，系统通过事件串联市场、策略、风控、订单和复盘 |
| Event Bus | 事件总线，用于发布和传递事件，当前支持 Redis stream |
| Event Ledger | 事件账本，把关键事件持久化，便于审计和回放 |
| Strategy Registry | 策略注册表，控制哪些策略可以进入运行态 |
| Strategy Engine | 策略引擎，把市场事件和组合状态转成交易意图 |
| TradeIntent | 交易意图，表示策略想买入或卖出，但还不是订单 |
| RiskEngine | 风控引擎，强制审批交易意图 |
| ExecutionEngine | 执行引擎，处理通过风控的订单状态流转 |
| Order State Machine | 订单状态机，记录订单从新建、审批、发送、成交或拒绝的过程 |
| Paper Trading | 模拟盘，不接真实券商，用虚拟账户记录订单、持仓和盈亏 |
| PnL | Profit and Loss，盈亏 |
| Realized PnL | 已实现盈亏，通常来自已平仓交易 |
| Unrealized PnL | 未实现盈亏，来自仍持有的浮动盈亏 |
| Candidate | 候选交易标的，由策略和数据证据生成 |
| Candidate ID | 候选 ID，用于把候选理由追踪到订单和盈亏 |
| Alpha | 策略超额收益能力，这里指经过样本验证后的正净期望 |
| Alpha Gate | Alpha 门禁，用样本量、期望、回撤、归因等条件阻止过早实盘化 |
| Expectancy | 期望收益，衡量平均每笔交易的收益质量 |
| Attribution | 归因，解释盈亏来自哪个策略、候选、ticker 或因素 |
| Regime | 市场状态，例如趋势市场、震荡市场、风险偏好变化 |
| Shadow | 影子运行，只观察策略会做什么，不实际下单 |
| Live-small | 小资金实盘，需要人工审批和风控确认 |
| LEAN | QuantConnect LEAN 回测引擎，当前只用于研究和回测 |
| vectorbt | Python 向量化回测工具，当前只用于研究 replay |
| OpenBB | 数据和研究访问工具，当前不负责下单或风控 |
| LangGraph | AI workflow 编排工具，当前只编排投研流程 |
| LLM | 大语言模型，当前只输出投研解释，不输出可执行订单 |
| SEC EDGAR | 美国 SEC 公告数据源 |
| Ticker | 股票代码，例如 AAPL、NVDA |
| Take Profit | 止盈条件 |
| Stop Loss | 止损条件 |
| Drawdown | 回撤，衡量从高点到低点的损失幅度 |
| Sharpe Ratio | 夏普比率，衡量风险调整后收益 |

## 16. 当前限制

当前系统仍有明确限制：

- 尚未达到 Alpha ready。
- 尚未进入 shadow。
- 尚未进入 live-small。
- 尚未开启 broker execution。
- AI 不负责自动交易决策。
- 回测结果不能视为真实稳定净期望。
- 仍需继续积累 paper trading 样本和闭环交易样本。

当前最重要任务不是扩大实盘权限，而是继续让系统稳定产生日候选、解释原因、模拟下单、记录盈亏、复盘策略，并让 Alpha gates 通过真实样本逐步收敛。
