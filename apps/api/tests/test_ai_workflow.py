import pytest
from pydantic import ValidationError

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.schemas import ResearchResult, TradePlanDraft
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


def test_research_workflow_uses_llm_client_for_research_only_and_keeps_human_review():
    class FakeLLMClient:
        def generate_research_result(self, request: ResearchRequest) -> ResearchResult:
            return ResearchResult(
                ticker=request.ticker.strip().upper(),
                status="complete_llm",
                summary="LLM structured research summary.",
                bull_case="LLM bull case.",
                bear_case="LLM bear case.",
                watch_items=["LLM watch item."],
                evidence_count=len(request.evidence),
                trade_plan_draft=TradePlanDraft(
                    entry_condition="LLM entry draft.",
                    invalidation_condition="LLM invalidation draft.",
                    risk_notes=["LLM risk note."],
                    requires_human_review=False,
                ),
            )

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

    result = run_research_workflow(request, llm_client=FakeLLMClient())

    assert result.status == "complete_llm"
    assert result.summary == "LLM structured research summary."
    assert result.trade_plan_draft.requires_human_review is True
    assert any("AI 仅用于投研解释" in note for note in result.trade_plan_draft.risk_notes)
    assert any("不是可直接执行的订单建议" in note for note in result.trade_plan_draft.risk_notes)


def test_research_workflow_falls_back_to_deterministic_result_when_llm_fails():
    class FailingLLMClient:
        def generate_research_result(self, request: ResearchRequest) -> ResearchResult:
            raise RuntimeError("llm unavailable")

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

    result = run_research_workflow(request, llm_client=FailingLLMClient())

    assert result.status == "complete"
    assert "Revenue grew but margin narrowed." in result.summary
    assert any("不是可直接执行的订单建议" in note for note in result.trade_plan_draft.risk_notes)
