# AI Research Notebook 设计

## 1. 目标

本阶段把 VelaQuant 的 AI 助手从“生成一次性结果”推进到“可沉淀的研究闭环”：

- 用户在右侧 AI 助手生成结构化研究结果后，可以一键保存为研究笔记。
- 后端同时保存原始 AI 输出到 `AiRun`，保留 prompt、结构化 JSON 和证据快照字段。
- Notes 页面能立即看到保存后的 AI 研究笔记。
- 保持人工复核边界：保存的是研究记录和交易计划草稿内容，不触发订单、不生成最终仓位。

完成后，核心链路变成：查看页面或组合 -> 询问 AI -> 生成结构化结论 -> 保存为研究笔记 -> 在 Notes 工作区复盘。

## 2. 背景

当前系统已经具备：

- 右侧 `AiSidecar`，可调用 `POST /api/mvp/research` 并展示 `ResearchResultPayload`。
- LangGraph 确定性研究 workflow，输出 summary、bull/base/bear、watch items 和 trade plan draft。
- SQLModel 本地工作区、`Note`、`AiRun`、`Workspace` service。
- Notes 页面可读取和新增普通研究笔记。

当前缺口：

- AI 结果只停留在侧栏状态里，刷新后消失。
- `AiRun` 模型存在但没有写入链路。
- AI 输出不能直接转成团队研究笔记。
- 用户无法从“识别组合风险/起草交易计划”继续沉淀到 Notes。

## 3. 推荐方案

### 方案 A：保存 AI result snapshot 为 Note + AiRun

这是本阶段采用方案。前端把已生成的 `ResearchResultPayload` 和原 prompt 发给后端；后端用 Pydantic 校验结果，创建 `AiRun` 原始记录，并把结果格式化成一条 `Note`。优点是改动小、可审计、复用现有 Notes 页面和 SQLite 本地工作区。

### 方案 B：每次研究自动保存

可以减少一次点击，但会把试探性 AI 输出全部写入数据库，造成噪声和误存。本阶段不采用。

### 方案 C：新增 TradePlan 表

更接近长期产品，但当前还没有审批、权限、订单边界和交易生命周期。贸然新增会让 MVP 变复杂。本阶段先把交易计划草稿作为笔记中的结构化段落保存。

## 4. 范围

### 4.1 本阶段包含

- 后端新增 research notebook service：
  - 接收 prompt + `ResearchResult`。
  - 创建 `AiRun`，保存 prompt、AI 输出 JSON、证据 JSON。
  - 创建 `Note`，标题和正文由 AI 输出格式化。
  - 返回 `ai_run_id` 和 `NotePayload`。
- MVP API：
  - `POST /api/mvp/research/notes`
- 前端：
  - client API helper：`saveResearchResultAsNote()`。
  - AI 侧栏结果区域新增“保存为笔记”按钮。
  - 保存成功后显示“已保存到研究笔记”状态。
  - 失败时给出可读错误状态。
- 测试：
  - 后端 service 和 route 测试。
  - Playwright 覆盖 AI 结果保存为笔记。

### 4.2 本阶段不包含

- 自动保存所有 AI 运行。
- 独立交易计划表。
- 交易审批流。
- 券商接口。
- 富文本笔记编辑。
- AI run 历史页面。
- 删除 AI run。
- 多用户归属。

## 5. 后端设计

新增 `app/services/research_notebook.py`：

- `ResearchNoteCreate`
  - `prompt: str`
  - `result: ResearchResult`
- `ResearchNotePayload`
  - `ai_run_id: UUID`
  - `note: NotePayload`

`save_research_result_as_note(session, data)` 流程：

1. 调用 `get_or_create_default_workspace(session)`。
2. 通过 `data.result.model_dump(mode="json")` 序列化 AI 输出。
3. 创建 `AiRun`：
   - `team_id`: 默认 team。
   - `prompt`: 用户点击的 prompt。
   - `output_json`: 结构化 AI 输出 JSON。
   - `evidence_json`: 本阶段使用 `"[]"`，保留字段给后续证据快照。
4. 创建 `Note`：
   - `ticker`: `result.ticker`。
   - `title`: `AI 研究 - {ticker} - {prompt}`。
   - `body`: 由以下段落组成：
     - 摘要。
     - 多头观点。
     - 空头风险。
     - 观察事项。
     - 交易计划草稿：入场条件、失效条件。
     - 风控提示。
     - 状态和证据数量。
5. commit 后 refresh，并返回 `ResearchNotePayload`。

错误处理：

- prompt 为空由 Pydantic 拒绝。
- result 缺字段由 `ResearchResult` 校验拒绝。
- 数据库错误不吞掉，由 FastAPI 返回 500；前端显示保存失败。

## 6. 前端设计

`AiSidecar` 保持现有结构，只增强结果区：

- 研究结果生成后展示一个 `保存为笔记` 主按钮。
- 点击后调用 `saveResearchResultAsNote(activePrompt, result)`。
- 保存中按钮禁用并显示 `保存中`。
- 保存成功后显示：
  - `已保存到研究笔记`
  - 保存的 note title。
- 如果用户重新点击另一个 AI prompt，清空保存状态。
- 离线 fallback 结果也允许保存，但笔记正文会包含 status，提醒用户这不是可直接执行结论。

Notes 页面不需要新增读取逻辑，因为它已经读取 `/api/mvp/notes`。

## 7. 测试策略

### 7.1 后端

新增 `tests/test_research_notebook_service.py`：

- 保存 AI result 会创建一条 `AiRun` 和一条 `Note`。
- Note 标题包含 ticker 和 prompt。
- Note body 包含 summary、bull_case、bear_case、watch_items、trade_plan_draft 和 risk_notes。
- prompt 为空被拒绝。

扩展 `tests/test_mvp_routes.py`：

- `POST /api/mvp/research/notes` 返回 `ai_run_id` 和 note payload。
- 缺失 result 字段时返回 422。

### 7.2 前端

扩展 Playwright：

- Mock `/api/mvp/research` 返回结构化结果。
- Mock `/api/mvp/research/notes` 返回 note payload。
- 点击 AI prompt 后点击 `保存为笔记`。
- 页面显示 `已保存到研究笔记` 和 note title。
- 验证请求 body 中包含 prompt 和 result ticker。

## 8. 验收标准

- `python -m pytest -v` 通过。
- `npm run lint` 通过。
- `npm run build` 通过。
- `npx playwright test` 通过。
- 浏览器实测：AI 侧栏生成结果后可以保存为笔记，Notes API 可读到保存结果。

## 9. 自检

- 复用现有 FastAPI、SQLModel、SQLite、LangGraph 和 Next.js。
- 不新增交易执行或审批复杂度。
- `AiRun` 开始发挥审计快照作用。
- Notes 工作区成为 AI 结果沉淀入口。
- 范围和验收标准已经明确。
