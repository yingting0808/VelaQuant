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
