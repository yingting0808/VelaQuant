# Local Workspace Persistence 设计

## 1. 目标

本阶段把 VelaQuant 从“静态样板 + 少量运行时文件”推进到“可保存的本地投研工作区”：

- 组合持仓可读取、编辑、导入并保存。
- 自选股可新增、删除并保存研究假设。
- 研究笔记可新增、查看并按 ticker 关联。
- Dashboard 从本地工作区读取组合和事件，而不是只使用硬编码样板。
- 保持单机本地优先，不引入账号系统、云同步或多租户复杂度。

本阶段完成后，用户可以关掉页面再打开，仍能看到自己的组合、自选股和笔记。

## 2. 背景

当前系统已经具备：

- FastAPI + SQLModel。
- 默认 `sqlite:///./local.db` 配置。
- 现成领域模型：`Team`、`Portfolio`、`Position`、`WatchlistItem`、`Note`。
- `create_db_and_tables()` 和 `get_session()`。
- `calculate_exposure()` 组合暴露计算。
- CSV 持仓解析器。
- 前端页面：Dashboard、Portfolio、Watchlist、Notes、Imports。

当前缺口：

- API 主要返回样板数据，未用本地数据库作为工作区事实源。
- Portfolio、Watchlist、Notes 页面仍是 `ModuleView` 静态列表。
- 数据导入只能解析 CSV，不能保存到组合。
- 前端没有保存/删除/创建的工作流。

## 3. 推荐方案

### 方案 A：继续使用 SQLModel + SQLite 本地工作区

这是本阶段采用方案。优点是与现有表结构、测试和设置完全一致，改动集中且可验证。缺点是暂时没有迁移框架；本阶段通过 `create_db_and_tables()` 和新增字段时保持向后兼容规避。

### 方案 B：前端 localStorage

实现最快，但数据只在浏览器里，后端 AI、Dashboard 和导入流程无法共享，后续接真实数据与权限会返工。

### 方案 C：直接上 Postgres + Alembic

更接近生产，但当前产品还在本地 MVP 阶段，会引入部署和迁移复杂度，不适合作为下一小步。

## 4. 范围

### 4.1 本阶段包含

- 本地默认 team/portfolio bootstrap。
- Workspace service：
  - 获取默认工作区摘要。
  - 读取主组合及持仓。
  - upsert / delete position。
  - 导入 CSV 并保存持仓。
  - 读取 / 新增 / 删除自选股。
  - 读取 / 新增研究笔记。
- MVP API：
  - `GET /api/mvp/workspace`
  - `GET /api/mvp/portfolio`
  - `PUT /api/mvp/portfolio/positions`
  - `DELETE /api/mvp/portfolio/positions/{ticker}`
  - `POST /api/mvp/portfolio/import`
  - `GET /api/mvp/watchlist`
  - `POST /api/mvp/watchlist`
  - `DELETE /api/mvp/watchlist/{ticker}`
  - `GET /api/mvp/notes`
  - `POST /api/mvp/notes`
- Dashboard 改为从主组合持仓生成 portfolio/exposure。
- 前端：
  - Portfolio 页面显示持仓表，支持新增/更新和删除。
  - Imports 页面支持粘贴 CSV 并保存到主组合。
  - Watchlist 页面显示自选股，支持新增和删除。
  - Notes 页面显示笔记，支持新增。
  - 保留离线 fallback，后端不可用时仍可展示占位状态。

### 4.2 本阶段不包含

- 用户登录。
- 多团队切换。
- 权限编辑。
- 数据库迁移工具。
- 云同步。
- 实盘交易。
- 文件上传组件。
- 富文本编辑器。
- 全文搜索。

## 5. 后端设计

### 5.1 Bootstrap

新增 `app/services/workspace.py`，提供：

- `DEFAULT_TEAM_NAME = "个人工作区"`
- `DEFAULT_PORTFOLIO_NAME = "主组合"`
- `get_or_create_default_workspace(session)`

第一次访问 workspace API 时：

1. 调用 `create_db_and_tables()` 确保表存在。
2. 查找默认 team，不存在则创建。
3. 查找默认 portfolio，不存在则创建。
4. 如果 portfolio 没有持仓，初始化 AAPL/MSFT 示例持仓，保持当前 Dashboard 初始体验。
5. 如果 watchlist 为空，初始化 NVDA/AMZN/META 示例自选股。
6. 初始化只在空表时发生，不覆盖用户数据。

### 5.2 数据模型输出

后端新增 Pydantic payload：

- `WorkspaceSummary`
- `PortfolioPayload`
- `PositionPayload`
- `PositionUpsert`
- `WatchlistItemPayload`
- `WatchlistUpsert`
- `NotePayload`
- `NoteCreate`

输出字段使用前端需要的稳定结构，不直接暴露 SQLModel 内部对象。

### 5.3 组合计算

`get_portfolio_payload(session, provider)`：

- 从数据库读取 position。
- 对每个 ticker 调用现有 market data provider 获取 quote。
- 如果 quote price 不可用，使用 `average_cost` 作为保守 fallback price。
- 用现有 `calculate_exposure()` 计算市值和权重。
- 返回 position 的 quantity、average_cost、price、market_value、weight、currency、updated_at。

### 5.4 写入规则

持仓 upsert：

- ticker trim + upper。
- quantity 必须大于等于 0。
- average_cost 必须大于等于 0。
- currency 默认 USD。
- 同一 portfolio + ticker 只保留一条 position；重复 upsert 更新原记录。

删除持仓：

- 不存在时返回 404。

CSV 导入：

- 复用 `parse_positions_csv()`。
- 解析出的 valid positions 全部 upsert。
- 返回 imported count、errors、最新 portfolio。
- 有部分错误时仍保存 valid rows。

自选股：

- ticker trim + upper。
- thesis 可为空。
- 重复 ticker 更新 thesis。
- 删除不存在返回 404。

笔记：

- title/body 必填。
- ticker 可选，存在则 upper。
- 本阶段只新增和读取，不做编辑删除。

### 5.5 Dashboard 集成

`GET /api/mvp/dashboard` 改为：

- 使用 `get_portfolio_payload()` 返回本地主组合。
- alerts 基于本地组合 ticker 生成。
- ai prompts 保持现有中文。
- data source 和 strategy lab 状态保持现有逻辑。

如果本地 DB 不可写或 provider 报错，API 仍应返回结构化错误或 fallback，不让前端白屏。

## 6. 前端设计

### 6.1 Client API

扩展 `apps/web/src/lib/client-api.ts`：

- `getPortfolio()`
- `upsertPosition()`
- `deletePosition()`
- `importPositionsCsv()`
- `getWatchlist()`
- `upsertWatchlistItem()`
- `deleteWatchlistItem()`
- `getNotes()`
- `createNote()`

所有 helper 都保留 fallback，后端不可用时返回可读状态。

### 6.2 Portfolio 页面

替换静态 `ModuleView`：

- 页面 header：组合。
- 持仓表：Ticker、数量、成本、现价、市值、权重。
- 右上角简洁表单：Ticker、数量、平均成本、保存。
- 行内删除按钮。
- 保存后刷新列表。

### 6.3 Imports 页面

替换静态 `ModuleView`：

- CSV textarea。
- 示例字段提示：`ticker,quantity,average_cost,currency`。
- “导入持仓”按钮。
- 显示导入成功数量和行级错误。
- 导入后展示最新组合摘要。

### 6.4 Watchlist 页面

保留 Market Snapshot 面板，新增可编辑自选股工作区：

- 自选股列表。
- 新增/更新 ticker + thesis。
- 删除按钮。
- 点击 ticker 可辅助填充 Market Snapshot 查询仍保持当前独立查询机制；本阶段不强制联动。

### 6.5 Notes 页面

替换静态 `ModuleView`：

- 笔记列表。
- 新增表单：Ticker、标题、正文。
- 新笔记提交后刷新列表。

## 7. 测试策略

### 7.1 后端

新增 `tests/test_workspace_service.py`：

- 默认 workspace 会 bootstrap。
- portfolio 空时初始化示例持仓。
- position upsert 更新同 ticker。
- delete position 删除成功，不存在报错。
- CSV import 保存 valid rows 并返回 row errors。
- watchlist upsert/delete。
- note create/list。

扩展 `tests/test_mvp_routes.py`：

- workspace route 返回 summary。
- portfolio route 返回持仓。
- position upsert/delete routes。
- CSV import route。
- watchlist routes。
- notes routes。
- dashboard 使用数据库组合 ticker。

### 7.2 前端

扩展 Playwright：

- Portfolio 页面能新增持仓并显示。
- Watchlist 页面能新增自选股并显示。
- Notes 页面能新增笔记并显示。
- Imports 页面能导入 CSV 并显示错误。
- Dashboard 仍能渲染。

## 8. 验收标准

- `python -m pytest -v` 通过。
- `npm run lint` 通过。
- `npm run build` 通过。
- `npx playwright test` 通过。
- `docker compose config` 通过。
- 浏览器实测：
  - Portfolio 可保存持仓。
  - Watchlist 可保存自选股。
  - Notes 可保存笔记。
  - Imports 可导入 CSV。
  - 重新打开页面数据仍存在。

## 9. 自检

- 使用现有 FastAPI、SQLModel、SQLite、Next.js，不引入新框架。
- 范围聚焦本地工作区，不做登录、多团队、云同步。
- 写入 API 都有校验与测试。
- 前端保持工具型密度和现有视觉语言。
- 没有开放问题或未完成占位。
