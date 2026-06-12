import json
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.ai.schemas import ResearchResult
from app.domain.models import AiRun, Note
from app.services.workspace import NotePayload, get_or_create_default_workspace


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
    ticker = data.result.ticker.strip().upper()
    ai_run = AiRun(
        team_id=workspace.team.id,
        prompt=data.prompt,
        output_json=json.dumps(data.result.model_dump(mode="json"), ensure_ascii=False),
        evidence_json="[]",
    )
    note = Note(
        team_id=workspace.team.id,
        ticker=ticker,
        title=f"AI 研究 - {ticker} - {data.prompt}",
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


def _note_payload(note: Note) -> NotePayload:
    return NotePayload(id=note.id, ticker=note.ticker, title=note.title, body=note.body, created_at=note.created_at)
