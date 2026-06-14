from typing import Protocol, TypedDict

from langgraph.graph import END, StateGraph

from app.ai.schemas import ResearchRequest, ResearchResult, TradePlanDraft


class ResearchLLMClient(Protocol):
    def generate_research_result(self, request: ResearchRequest) -> ResearchResult:
        raise NotImplementedError


class ResearchState(TypedDict):
    request: ResearchRequest
    result: ResearchResult | None
    llm_client: ResearchLLMClient | None


def analyze(state: ResearchState) -> ResearchState:
    request = state["request"]
    ticker = request.ticker.strip().upper()
    if not request.evidence:
        state["result"] = ResearchResult(
            ticker=ticker,
            status="insufficient_evidence",
            summary="证据不足，无法生成可靠的投研观点。",
            bull_case="缺少证据，暂不生成多头观点。",
            bear_case="缺少证据，暂不生成空头风险判断。",
            watch_items=["在依赖 AI 输出前，先补充 filings、市场数据或团队笔记。"],
            evidence_count=0,
            trade_plan_draft=TradePlanDraft(
                entry_condition="暂不生成入场条件。",
                invalidation_condition="暂不生成失效条件。",
                risk_notes=["证据包为空。", "这不是可直接执行的订单建议。"],
            ),
        )
        return state

    llm_client = state.get("llm_client")
    if llm_client is not None:
        try:
            state["result"] = _enforce_research_only_guardrails(llm_client.generate_research_result(request))
            return state
        except Exception:
            pass

    combined = " ".join(item.summary for item in request.evidence)
    state["result"] = ResearchResult(
        ticker=ticker,
        status="complete",
        summary=f"{ticker}: {combined}",
        bull_case="已有正面证据，但团队仍需验证其持续性与估值合理性。",
        bear_case="如果基本面转弱或估值压缩，空头风险仍然存在。",
        watch_items=[
            "复核最新 filing 趋势。",
            "对照新闻影响与组合暴露。",
            "复盘投资假设是否发生变化。",
        ],
        evidence_count=len(request.evidence),
        trade_plan_draft=TradePlanDraft(
            entry_condition="仅在人工复核证据并确认投资假设后，才考虑后续动作。",
            invalidation_condition="如果新的 filings 或新闻与证据包相矛盾，该草稿应失效。",
            risk_notes=["这不是可直接执行的订单建议。", "必须经过人工审批。"],
        ),
    )
    return state


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("analyze", analyze)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", END)
    return graph.compile()


def run_research_workflow(request: ResearchRequest, llm_client: ResearchLLMClient | None = None) -> ResearchResult:
    graph = build_graph()
    final_state = graph.invoke({"request": request, "result": None, "llm_client": llm_client})
    result = final_state["result"]
    if result is None:
        raise RuntimeError("research workflow did not produce a result")
    return result


def _enforce_research_only_guardrails(result: ResearchResult) -> ResearchResult:
    guardrail_notes = [
        "AI 仅用于投研解释，不参与 TradeIntent、风控或执行。",
        "这不是可直接执行的订单建议。",
        "必须经过人工审批。",
    ]
    existing_notes = result.trade_plan_draft.risk_notes
    notes = list(dict.fromkeys([*existing_notes, *guardrail_notes]))
    draft = result.trade_plan_draft.model_copy(
        update={
            "requires_human_review": True,
            "risk_notes": notes,
        }
    )
    return result.model_copy(update={"trade_plan_draft": draft})
