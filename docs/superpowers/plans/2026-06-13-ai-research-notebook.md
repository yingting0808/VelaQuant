# AI Research Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save an AI sidecar research result into the local research notebook, while preserving the raw AI result snapshot in `AiRun`.

**Architecture:** Add a backend service that accepts a validated `ResearchResult`, writes `AiRun`, formats a readable `Note`, and exposes it through one MVP route. The frontend keeps AI generation in `AiSidecar`, adds a typed save helper, and shows an explicit saved/failed state.

**Tech Stack:** FastAPI, Pydantic, SQLModel, SQLite, LangGraph result schemas, Next.js App Router, React client components, Playwright.

---

## File Map

- Create `apps/api/app/services/research_notebook.py`: validation payloads and persistence/formatting service.
- Create `apps/api/tests/test_research_notebook_service.py`: service-level tests for `AiRun` + `Note`.
- Modify `apps/api/app/api/routes/mvp.py`: route import and `POST /api/mvp/research/notes`.
- Modify `apps/api/tests/test_mvp_routes.py`: route tests.
- Modify `apps/web/src/lib/client-api.ts`: save payload types, validator, and helper.
- Modify `apps/web/src/components/ai-sidecar.tsx`: save button and saved/error state.
- Modify `apps/web/tests/mvp.spec.ts`: E2E coverage for saving AI output as a note.

---

### Task 1: Backend Research Notebook Service

**Files:**
- Create: `apps/api/tests/test_research_notebook_service.py`
- Create: `apps/api/app/services/research_notebook.py`

- [ ] **Step 1: Write failing service tests**

Create `apps/api/tests/test_research_notebook_service.py`:

```python
import json

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine, select

from app.ai.schemas import ResearchResult, TradePlanDraft
from app.domain.models import AiRun, Note
from app.services.research_notebook import ResearchNoteCreate, save_research_result_as_note


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _result() -> ResearchResult:
    return ResearchResult(
        ticker="AAPL",
        status="complete",
        summary="AAPL: 服务收入韧性仍在。",
        bull_case="服务收入和回购支撑多头观点。",
        bear_case="估值压缩和硬件周期是主要风险。",
        watch_items=["复核 10-Q", "跟踪服务毛利率"],
        evidence_count=2,
        trade_plan_draft=TradePlanDraft(
            entry_condition="人工复核后才考虑后续动作。",
            invalidation_condition="若最新 filing 与假设相反则失效。",
            risk_notes=["这不是可直接执行的订单建议。", "必须经过人工审批。"],
        ),
    )


def test_save_research_result_as_note_creates_ai_run_and_note():
    with _session() as session:
        payload = save_research_result_as_note(
            session,
            ResearchNoteCreate(prompt="识别组合风险", result=_result()),
        )

        ai_run = session.get(AiRun, payload.ai_run_id)
        note = session.get(Note, payload.note.id)

        assert ai_run is not None
        assert ai_run.prompt == "识别组合风险"
        assert json.loads(ai_run.output_json)["ticker"] == "AAPL"
        assert json.loads(ai_run.evidence_json) == []
        assert note is not None
        assert note.ticker == "AAPL"
        assert note.title == "AI 研究 - AAPL - 识别组合风险"
        assert "AAPL: 服务收入韧性仍在。" in note.body
        assert "服务收入和回购支撑多头观点。" in note.body
        assert "估值压缩和硬件周期是主要风险。" in note.body
        assert "复核 10-Q" in note.body
        assert "人工复核后才考虑后续动作。" in note.body
        assert "必须经过人工审批。" in note.body


def test_saved_ai_note_is_visible_in_note_query_order():
    with _session() as session:
        payload = save_research_result_as_note(
            session,
            ResearchNoteCreate(prompt="生成多/中/空情景", result=_result()),
        )

        notes = list(session.exec(select(Note).order_by(Note.created_at.desc())).all())

        assert notes[0].id == payload.note.id
        assert notes[0].title == "AI 研究 - AAPL - 生成多/中/空情景"


def test_research_note_create_rejects_blank_prompt():
    with pytest.raises(ValidationError):
        ResearchNoteCreate(prompt="   ", result=_result())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-ai-research-notebook\apps\api
python -m pytest tests\test_research_notebook_service.py -v
```

Expected: FAIL because `app.services.research_notebook` does not exist.

- [ ] **Step 3: Implement service**

Create `apps/api/app/services/research_notebook.py`:

```python
import json
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.ai.schemas import ResearchResult
from app.domain.models import AiRun, Note
from app.services.workspace import NotePayload, _note_payload, get_or_create_default_workspace


class ResearchNoteCreate(BaseModel):
    prompt: str = Field(min_length=1)
    result: ResearchResult

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


class ResearchNotePayload(BaseModel):
    ai_run_id: UUID
    note: NotePayload


def save_research_result_as_note(session: Session, data: ResearchNoteCreate) -> ResearchNotePayload:
    workspace = get_or_create_default_workspace(session)
    output_json = json.dumps(data.result.model_dump(mode="json"), ensure_ascii=False)
    ai_run = AiRun(
        team_id=workspace.team.id,
        prompt=data.prompt,
        output_json=output_json,
        evidence_json="[]",
    )
    note = Note(
        team_id=workspace.team.id,
        ticker=data.result.ticker.strip().upper(),
        title=f"AI 研究 - {data.result.ticker.strip().upper()} - {data.prompt}",
        body=_format_note_body(data.result),
    )
    session.add(ai_run)
    session.add(note)
    session.commit()
    session.refresh(ai_run)
    session.refresh(note)
    return ResearchNotePayload(ai_run_id=ai_run.id, note=_note_payload(note))


def _format_note_body(result: ResearchResult) -> str:
    watch_items = "\n".join(f"- {item}" for item in result.watch_items) or "- 无"
    risk_notes = "\n".join(f"- {item}" for item in result.trade_plan_draft.risk_notes) or "- 无"
    return "\n\n".join(
        [
            f"摘要\n{result.summary}",
            f"多头观点\n{result.bull_case}",
            f"空头风险\n{result.bear_case}",
            f"观察事项\n{watch_items}",
            "交易计划草稿\n"
            f"入场条件：{result.trade_plan_draft.entry_condition}\n"
            f"失效条件：{result.trade_plan_draft.invalidation_condition}",
            f"风控提示\n{risk_notes}",
            f"状态：{result.status}\n证据数量：{result.evidence_count}",
        ]
    )
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
python -m pytest tests\test_research_notebook_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/research_notebook.py apps/api/tests/test_research_notebook_service.py
git commit -m "feat(api): save AI research results as notes"
```

---

### Task 2: MVP Route

**Files:**
- Modify: `apps/api/tests/test_mvp_routes.py`
- Modify: `apps/api/app/api/routes/mvp.py`

- [ ] **Step 1: Write failing route tests**

Append to `apps/api/tests/test_mvp_routes.py`:

```python
def _research_result_payload() -> dict:
    return {
        "ticker": "AAPL",
        "status": "complete",
        "summary": "AAPL: 服务收入韧性仍在。",
        "bull_case": "服务收入支撑多头观点。",
        "bear_case": "估值压缩仍是风险。",
        "watch_items": ["复核 10-Q"],
        "evidence_count": 1,
        "trade_plan_draft": {
            "entry_condition": "人工复核后才考虑后续动作。",
            "invalidation_condition": "证据相反则失效。",
            "risk_notes": ["必须经过人工审批。"],
            "requires_human_review": True,
        },
    }


def test_mvp_research_note_route_saves_ai_result():
    response = client.post(
        "/api/mvp/research/notes",
        json={"prompt": "识别组合风险", "result": _research_result_payload()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_run_id"]
    assert payload["note"]["ticker"] == "AAPL"
    assert payload["note"]["title"] == "AI 研究 - AAPL - 识别组合风险"
    assert "AAPL: 服务收入韧性仍在。" in payload["note"]["body"]


def test_mvp_research_note_route_rejects_malformed_result():
    response = client.post(
        "/api/mvp/research/notes",
        json={"prompt": "识别组合风险", "result": {"ticker": "AAPL"}},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run route tests to verify failure**

Run:

```powershell
python -m pytest tests\test_mvp_routes.py -k "research_note" -v
```

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Implement route**

In `apps/api/app/api/routes/mvp.py`, import:

```python
from app.services.research_notebook import ResearchNoteCreate, save_research_result_as_note
```

Add route after `notes_create`:

```python
@router.post("/research/notes")
def research_note_create(body: ResearchNoteCreate, session: Session = Depends(get_session)) -> dict:
    return save_research_result_as_note(session, body).model_dump()
```

- [ ] **Step 4: Run route tests**

Run:

```powershell
python -m pytest tests\test_mvp_routes.py -k "research_note" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/api/routes/mvp.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): expose AI research note route"
```

---

### Task 3: Frontend AI Save Flow

**Files:**
- Modify: `apps/web/tests/mvp.spec.ts`
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/src/components/ai-sidecar.tsx`

- [ ] **Step 1: Write failing Playwright test**

Add a test after the AI prompt success test:

```typescript
test("AI research result can be saved as a note", async ({ page }) => {
  let savedRequest: { prompt?: string; result?: { ticker?: string } } | null = null;
  await page.route("**/api/mvp/research", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        ticker: "AAPL",
        status: "complete",
        summary: "AAPL: 模拟组合风险研究结果。",
        bull_case: "服务收入韧性支持多头观点。",
        bear_case: "估值压缩仍是主要风险。",
        watch_items: ["复核 filing 趋势"],
        evidence_count: 2,
        trade_plan_draft: {
          entry_condition: "人工复核确认投资假设。",
          invalidation_condition: "新的 filing 与证据相矛盾。",
          risk_notes: ["必须经过人工审批。"],
          requires_human_review: true
        }
      }
    });
  });
  await page.route("**/api/mvp/research/notes", async (route) => {
    savedRequest = route.request().postDataJSON() as { prompt?: string; result?: { ticker?: string } };
    await route.fulfill({
      contentType: "application/json",
      json: {
        ai_run_id: "run-aapl",
        note: {
          id: "note-aapl",
          ticker: "AAPL",
          title: "AI 研究 - AAPL - 识别组合风险",
          body: "AAPL: 模拟组合风险研究结果。",
          created_at: "2026-06-13T00:00:00Z"
        }
      }
    });
  });

  await gotoDashboard(page);
  await page.getByRole("button", { name: "识别组合风险" }).click();
  await page.getByRole("button", { name: "保存为笔记" }).click();

  expect(savedRequest?.prompt).toBe("识别组合风险");
  expect(savedRequest?.result?.ticker).toBe("AAPL");
  await expect(page.getByText("已保存到研究笔记")).toBeVisible();
  await expect(page.getByText("AI 研究 - AAPL - 识别组合风险")).toBeVisible();
});
```

- [ ] **Step 2: Run Playwright test to verify failure**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-ai-research-notebook\apps\web
npx playwright test --grep "saved as a note"
```

Expected: FAIL because the save helper and button do not exist.

- [ ] **Step 3: Add client API helper**

In `apps/web/src/lib/client-api.ts`, add:

```typescript
export type ResearchNotePayload = {
  ai_run_id: string;
  note: NotePayload;
};

function isResearchNotePayload(value: unknown): value is ResearchNotePayload {
  return isRecord(value) && typeof value.ai_run_id === "string" && isNotePayload(value.note);
}

export async function saveResearchResultAsNote(
  prompt: string,
  result: ResearchResultPayload
): Promise<ResearchNotePayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/research/notes`, {
      body: JSON.stringify({ prompt, result }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isResearchNotePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Add AI sidecar save UI**

In `apps/web/src/components/ai-sidecar.tsx`:

- Import `Save` and `saveResearchResultAsNote`.
- Track `isSaving`, `savedTitle`, and `saveError`.
- Clear saved state when a new prompt starts.
- Render a `保存为笔记` button inside the result block.
- On click, call `saveResearchResultAsNote(activePrompt ?? "AI 研究", result)`.
- Show `已保存到研究笔记` and note title when successful.

- [ ] **Step 5: Run Playwright test**

Run:

```powershell
npx playwright test --grep "saved as a note"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/lib/client-api.ts apps/web/src/components/ai-sidecar.tsx apps/web/tests/mvp.spec.ts
git commit -m "feat(web): save AI research results to notes"
```

---

### Task 4: Verification and Integration

**Files:**
- No planned code files.

- [ ] **Step 1: Run backend tests**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-ai-research-notebook\apps\api
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend checks**

```powershell
cd D:\Documents\AI美股\.worktrees\codex-ai-research-notebook\apps\web
npm run lint
npm run build
npx playwright test
```

Expected: all PASS.

- [ ] **Step 3: Handle Docker environment**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-ai-research-notebook
docker compose config
```

Expected on a fully provisioned machine: PASS. If `docker` is not recognized, record this as an environment blocker, not a code failure.

- [ ] **Step 4: Merge locally after verification**

```powershell
cd D:\Documents\AI美股
git checkout master
git merge --ff-only codex/ai-research-notebook
```

- [ ] **Step 5: Verify merged master**

Run the same backend/frontend checks from `D:\Documents\AI美股`.

- [ ] **Step 6: Cleanup**

```powershell
cd D:\Documents\AI美股
git worktree remove D:\Documents\AI美股\.worktrees\codex-ai-research-notebook
git worktree prune
git branch -d codex/ai-research-notebook
```

- [ ] **Step 7: Restart local services**

Stop old `127.0.0.1:8000` and `127.0.0.1:3000` processes, start API and web from `master`, then verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/mvp/workspace
Invoke-WebRequest http://127.0.0.1:3000/
```

Expected: API health ok, workspace JSON returned, web status 200.
