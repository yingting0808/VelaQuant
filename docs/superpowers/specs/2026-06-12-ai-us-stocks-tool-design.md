# 美股 AI 工具设计文档

日期：2026-06-12
状态：已通过初步设计确认

## 1. 背景与目标

本项目要设计一个面向小团队内部使用的美股 AI 投研与组合监控工具。产品最终可以覆盖四类能力：

- 个人/团队投研助手：财报、新闻、估值、公司对比、AI 总结。
- 交易决策辅助：盘前/盘中信号、异动解释、风险提示。
- 量化策略工具：因子筛选、回测、策略生成。
- 投资组合监控：持仓、风险、财报日历、预警和复盘。

第一期不试图一次性完整实现四个大系统，而是以“投研 + 组合监控”为主线，先形成可每日使用的闭环：

看公司和组合 -> 发现事件和风险 -> 向 AI 提问 -> 生成结构化结论 -> 保存为团队笔记或交易计划草稿。

核心约束：使用成熟框架和成熟数据/AI/图表能力，不从零自研行情、回测、AI 编排或基础 Web 框架。

## 2. 已确认的产品决策

- 使用对象：小团队内部使用。
- 用途边界：纯内部投研，不对外给客户或公众作为个性化投资建议。
- 数据源策略：混合方案。低成本数据先起步，接口层预留付费行情 API 和券商只读接入。
- AI 边界：长期支持执行型路径，但第一版不真实下单，只生成交易计划草稿。
- 交互形态：Dashboard + Chat 混合。
- 页面布局：左侧导航，中间数据工作区，右侧常驻 AI 助手。
- 组合输入：手动自选股/模拟持仓 + CSV/Excel 导入先做，券商只读预留。
- 预警实时性：每日摘要 + 事件驱动先做，准实时盘中监控预留。
- 部署方式：Docker Compose 本地/内网先跑通，架构兼容后续云端部署。
- 工程路线：自有产品外壳 + 成熟底座组合。

## 3. 总体架构

第一期采用自有产品外壳加成熟底座组合：

- 前端：Next.js + shadcn/ui。
- 数据表格：TanStack Table。
- 图表：TradingView Lightweight Charts 或 Apache ECharts。
- 后端 API：FastAPI。
- 数据层：OpenBB + 自定义 data adapters。
- AI 工作流：LangGraph。
- 数据库：Postgres。
- 缓存与任务队列：Redis 或兼容队列。
- 文件与材料存储：本地对象存储目录，后续可替换为 S3 兼容存储。
- 部署：Docker Compose。

### 3.1 前端边界

前端负责产品体验、交互状态、可视化和 AI 助手侧栏，不直接绑定具体外部数据 provider。

主要区域：

- 左侧导航：总览、自选股、组合、预警、研究笔记、数据导入、设置。
- 中间工作区：股票页、组合页、预警页、导入页、团队笔记页。
- 右侧 AI 助手：根据当前页面上下文回答问题、生成摘要、解释预警、生成交易计划草稿。

### 3.2 后端边界

FastAPI 作为统一 API 层，负责：

- 鉴权和团队权限。
- 自选股、组合、笔记、预警、导入任务和审计日志。
- 外部数据适配器的统一入口。
- AI 工作流调用入口。
- 后台任务状态查询。

### 3.3 数据层边界

数据层通过 adapter 隔离外部数据源，UI 和 AI 不直接调用 provider。第一期支持：

- SEC EDGAR filings 和 XBRL 数据。
- OpenBB provider 可获得的行情、新闻、财报日历、基础财务数据。
- CSV/Excel 导入的持仓和交易记录。

预留：

- 付费行情 API，例如 Polygon/Massive、Finnhub、FMP、IEX Cloud 等。
- 券商只读接口，例如 IBKR 或 Plaid Investments。
- 准实时盘中异动监控。

## 4. 数据流设计

### 4.1 输入来源

团队输入：

- 手动自选股。
- 模拟持仓。
- CSV/Excel 导入的持仓和交易记录。
- 团队研究笔记。
- 预警规则。

外部数据：

- SEC EDGAR filings/XBRL。
- OpenBB providers。
- 新闻源。
- 财报日历。
- 后续付费行情 API。

### 4.2 标准化

所有输入进入标准化层后再入库，标准化内容包括：

- ticker 映射。
- CIK 映射。
- 交易所、币种、时区统一。
- 持仓口径统一。
- 数据来源、抓取时间、更新时间记录。
- 原始数据与派生数据区分。

### 4.3 存储

Postgres 存储结构化数据：

- teams
- users
- team_memberships
- watchlists
- portfolios
- positions
- imported_files
- securities
- company_facts
- filings
- news_items
- alerts
- notes
- ai_runs
- trade_plan_drafts
- audit_logs

对象存储保存：

- CSV/Excel 原始上传文件。
- 导入错误报告。
- 财报原始材料或缓存。
- AI 证据包快照。
- 导出报告。

### 4.4 派生数据

后台任务生成：

- 估值摘要。
- 财报变化摘要。
- 新闻影响摘要。
- 组合暴露。
- 风险标签。
- 预警事件。
- 每日盘前/盘后摘要。

## 5. AI 工作流与执行边界

AI 使用 LangGraph 编排，流程为：

1. 接收当前上下文：股票页、组合页、预警事件、团队笔记、用户问题、权限范围。
2. 构建证据包：财报片段、关键指标、新闻、价格数据、历史笔记、来源链接和更新时间。
3. 多步分析：检索、分析、风险检查、结构化输出。
4. 输出保存：保存为团队笔记、预警解释或交易计划草稿。

### 5.1 第一期 AI 输出

允许输出：

- 投研摘要。
- 多空观点。
- 预警解释。
- 观察清单。
- 风险点。
- 待验证问题。
- 交易计划草稿。

交易计划草稿可以包含：

- 入场条件。
- 失效条件。
- 风险点。
- 仓位假设。
- 需要人工确认的数据。

### 5.2 明确禁止

第一期不做：

- 真实下单。
- 券商写操作。
- AI 自动决定买卖。
- AI 自动给出最终仓位。
- 对外客户报告发布。

### 5.3 未来执行能力边界

未来如接入券商或真实执行能力，任何高风险动作必须进入 human-in-the-loop：

- 流程暂停。
- 展示证据、风险、账户影响和订单草稿。
- 有权限成员批准、修改或拒绝。
- 所有动作写入审计日志。
- 支持一键停用执行能力。

## 6. 第一期页面和功能范围

### 6.1 必须包含

- 团队空间与成员角色。
- 自选股。
- 手动/CSV/Excel 持仓导入。
- 基础组合页：持仓、行业/个股暴露、事件影响。
- 股票详情页：行情图、关键指标、财报、新闻、团队笔记、AI 观点。
- 预警页：每日摘要、SEC filing、财报日历、新闻/价格事件、处理状态。
- 右侧 AI 助手。
- 团队研究笔记。
- 数据导入页。
- 设置页：团队、数据源、API key、权限。
- 来源引用、更新时间和审计日志。

### 6.2 预留但不实现

- 券商只读接入。
- 付费行情 API。
- 准实时盘中异动。
- 量化回测入口。
- 真实交易执行。
- 对外报告发布。

### 6.3 明确不做

- 移动 App。
- 复杂多租户 SaaS。
- 全市场高频扫描。
- 自动仓位建议。
- 自动交易。

## 7. 权限与审计

第一期角色：

- Owner：管理成员、API key、数据源、团队设置、审计查看。
- Analyst：维护自选股和组合、导入数据、生成 AI 草稿、处理预警、保存团队笔记。
- Viewer：只读 Dashboard、股票页、组合页和已发布团队笔记。

审计事件：

- 登录和退出。
- 导入文件。
- 修改自选股和组合。
- 配置数据源和 API key。
- 生成或保存 AI 草稿。
- 处理、分配、关闭预警。
- 权限变更。
- 未来执行能力相关的批准、修改、拒绝。

## 8. 错误处理

数据源失败：

- 显示最近成功更新时间和来源。
- 不用过期数据冒充实时数据。
- 进入后台任务重试。

AI 证据不足：

- 输出“不足以判断”。
- 列出缺失数据。
- 不编造结论。

导入失败：

- 按行返回错误原因。
- 支持部分成功。
- 可下载错误报告。

后台任务失败：

- 自动重试。
- 超过阈值后进入预警队列。
- 保留日志。

权限不足：

- 明确提示动作不可用。
- 不泄露其他团队成员或数据。

## 9. 测试策略

### 9.1 单元测试

覆盖：

- ticker/CIK 映射。
- CSV/Excel 解析。
- 组合暴露计算。
- 预警规则。
- AI 输出 schema 校验。
- 权限判断。

### 9.2 API 测试

使用 FastAPI TestClient 或等价工具覆盖：

- 鉴权。
- 权限。
- 导入。
- 数据查询。
- 预警状态流转。
- 审计日志。
- 错误响应。

### 9.3 集成测试

覆盖：

- 外部 API mock。
- 数据源失败和重试。
- 速率限制。
- 缓存。
- 来源引用。
- 更新时间。

### 9.4 E2E 测试

使用 Playwright 覆盖至少一条关键路径：

导入持仓 -> 查看组合 -> 触发预警 -> 询问 AI -> 保存团队笔记。

## 10. 验收标准

第一期完成时应满足：

- 团队可以在本地/内网通过 Docker Compose 一键启动完整应用。
- 用户能维护自选股和模拟/导入持仓。
- 股票页和组合页显示来源清晰、更新时间明确的数据。
- 每日摘要和事件预警能生成、分配、处理、归档。
- 右侧 AI 助手输出结构化、带证据引用、可保存为团队笔记。
- AI 可以生成交易计划草稿，但不能真实下单。
- 权限、导入失败、数据源失败、AI 证据不足都有明确行为。
- 核心单元测试、API 测试、数据适配 mock 测试和至少一条 E2E 流程通过。

## 11. 主要风险与控制

数据质量风险：

- 通过来源、更新时间、数据源标记和证据引用降低误用风险。

AI 幻觉风险：

- 通过证据包、结构化输出、证据不足声明和审计日志控制。

范围膨胀风险：

- 第一版只做投研 + 组合监控主线，交易执行、量化回测和准实时行情预留接口。

数据授权风险：

- 数据源 adapter 必须记录 provider、license/usage notes 和 API key 配置方式。

安全风险：

- API key 只保存在后端环境或加密配置中，不进入前端 bundle。
- 权限判断在后端执行。
- 审计日志记录高风险动作。

## 12. 参考资料

- Next.js Docs: https://nextjs.org/docs
- FastAPI Docs: https://fastapi.tiangolo.com/
- OpenBB Providers: https://docs.openbb.co/odp/python/extensions/providers
- OpenBB Extensions: https://docs.openbb.co/odp/python/extensions
- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- LangGraph Human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- Docker Compose: https://docs.docker.com/compose/
- shadcn/ui: https://ui.shadcn.com/
- TanStack Table: https://tanstack.com/table/latest
- TradingView Lightweight Charts: https://tradingview.github.io/lightweight-charts/
- OWASP API Security Top 10: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/
- Playwright Testing: https://playwright.dev/docs/writing-tests
