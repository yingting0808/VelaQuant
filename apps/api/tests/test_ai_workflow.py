import pytest
from pydantic import ValidationError

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow


def test_research_workflow_returns_structured_answer_with_evidence():
    request = ResearchRequest(
        ticker="AAPL",
        question="What should we watch?",
        evidence=[
            EvidenceItemInput(
                title="AAPL filing",
                summary="Revenue grew but margin narrowed.",
                source="mock_filing",
                source_url="https://example.local/aapl",
            )
        ],
    )

    result = run_research_workflow(request)

    assert result.ticker == "AAPL"
    assert result.status == "complete"
    assert "Revenue grew but margin narrowed." in result.summary
    assert result.evidence_count == 1
    assert result.trade_plan_draft.entry_condition
    assert result.trade_plan_draft.requires_human_review is True
    assert any("不是可直接执行的订单建议" in note for note in result.trade_plan_draft.risk_notes)


def test_research_workflow_normalizes_whitespace_ticker():
    request = ResearchRequest(
        ticker=" aapl ",
        question=" What should we watch? ",
        evidence=[
            EvidenceItemInput(
                title="AAPL filing",
                summary="Revenue grew but margin narrowed.",
                source="mock_filing",
                source_url="https://example.local/aapl",
            )
        ],
    )

    result = run_research_workflow(request)

    assert request.question == "What should we watch?"
    assert result.ticker == "AAPL"


def test_research_request_rejects_whitespace_only_ticker():
    with pytest.raises(ValidationError):
        ResearchRequest(ticker="   ", question="Should we buy?", evidence=[])


def test_research_request_rejects_whitespace_only_question():
    with pytest.raises(ValidationError):
        ResearchRequest(ticker="AAPL", question="   ", evidence=[])


def test_research_workflow_refuses_when_evidence_is_missing():
    request = ResearchRequest(ticker="AAPL", question="Should we buy?", evidence=[])

    result = run_research_workflow(request)

    assert result.status == "insufficient_evidence"
    assert result.summary == "证据不足，无法生成可靠的投研观点。"
    assert result.evidence_count == 0
    assert any("不是可直接执行的订单建议" in note for note in result.trade_plan_draft.risk_notes)
