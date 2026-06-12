from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.ai.schemas import ResearchRequest, ResearchResult, TradePlanDraft


class ResearchState(TypedDict):
    request: ResearchRequest
    result: ResearchResult | None


def analyze(state: ResearchState) -> ResearchState:
    request = state["request"]
    ticker = request.ticker.strip().upper()
    if not request.evidence:
        state["result"] = ResearchResult(
            ticker=ticker,
            status="insufficient_evidence",
            summary="Insufficient evidence to produce a research view.",
            bull_case="No bull case generated because evidence is missing.",
            bear_case="No bear case generated because evidence is missing.",
            watch_items=["Add filings, market data, or team notes before relying on AI output."],
            evidence_count=0,
            trade_plan_draft=TradePlanDraft(
                entry_condition="No entry condition generated.",
                invalidation_condition="No invalidation condition generated.",
                risk_notes=["Evidence package is empty.", "This is not executable order guidance."],
            ),
        )
        return state

    combined = " ".join(item.summary for item in request.evidence)
    state["result"] = ResearchResult(
        ticker=ticker,
        status="complete",
        summary=f"{ticker}: {combined}",
        bull_case="Positive evidence exists, but the team must validate durability and valuation.",
        bear_case="Risk remains if fundamentals weaken or valuation compresses.",
        watch_items=[
            "Confirm the latest filing trend.",
            "Compare news impact with portfolio exposure.",
            "Review whether the thesis changed.",
        ],
        evidence_count=len(request.evidence),
        trade_plan_draft=TradePlanDraft(
            entry_condition="Only consider action after a human reviews the evidence and confirms the thesis.",
            invalidation_condition="Invalidate the draft if new filings or news contradict the evidence package.",
            risk_notes=["This is not executable order guidance.", "Human approval is required."],
        ),
    )
    return state


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("analyze", analyze)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", END)
    return graph.compile()


def run_research_workflow(request: ResearchRequest) -> ResearchResult:
    graph = build_graph()
    final_state = graph.invoke({"request": request, "result": None})
    result = final_state["result"]
    if result is None:
        raise RuntimeError("research workflow did not produce a result")
    return result
