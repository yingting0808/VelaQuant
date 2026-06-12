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
    assert result.summary
    assert result.evidence_count == 1
    assert result.trade_plan_draft.entry_condition
    assert result.trade_plan_draft.requires_human_review is True


def test_research_workflow_refuses_when_evidence_is_missing():
    request = ResearchRequest(ticker="AAPL", question="Should we buy?", evidence=[])

    result = run_research_workflow(request)

    assert result.status == "insufficient_evidence"
    assert result.summary == "Insufficient evidence to produce a research view."
    assert result.evidence_count == 0
