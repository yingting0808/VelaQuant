from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.alpha_gate_progress import AlphaGateProgressPayload, get_alpha_gate_progress
from app.services.alpha_validation_forecast import AlphaValidationForecastPayload, get_alpha_validation_forecast
from app.services.event_ledger import EventLedgerStatus, get_event_ledger_status
from app.services.paper_action_plan import PaperActionPlanPayload, get_paper_action_plan
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, get_paper_execution_diagnostics
from app.services.paper_risk_profile import PaperRiskProfilePayload, get_paper_risk_profile
from app.services.workspace import get_or_create_default_workspace


ShadowReviewStatus = Literal["blocked", "ready_for_manual_review"]
ShadowReviewRiskSeverity = Literal["info", "medium", "high"]


class ShadowReviewChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    passed: bool
    evidence: list[str]


class ShadowReviewResidualRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: ShadowReviewRiskSeverity
    detail: str
    evidence: list[str]


class ShadowReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ShadowReviewStatus
    strategy_id: str
    can_request_shadow_review: bool
    recommended_stage: str
    auto_promotion_enabled: bool
    checklist: list[ShadowReviewChecklistItem]
    residual_risks: list[ShadowReviewResidualRisk]
    summary: str


def get_shadow_review_packet(session: Session) -> ShadowReviewPayload:
    team_id = get_or_create_default_workspace(session).team.id
    return build_shadow_review_packet(
        alpha_gates=get_alpha_gate_progress(session, team_id=team_id),
        alpha_forecast=get_alpha_validation_forecast(session, team_id=team_id),
        action_plan=get_paper_action_plan(session),
        execution=get_paper_execution_diagnostics(session, team_id=team_id),
        event_ledger=get_event_ledger_status(session),
        risk_profile=get_paper_risk_profile(session, team_id=team_id),
    )


def build_shadow_review_packet(
    *,
    alpha_gates: AlphaGateProgressPayload,
    alpha_forecast: AlphaValidationForecastPayload,
    action_plan: PaperActionPlanPayload,
    execution: PaperExecutionDiagnosticsPayload,
    event_ledger: EventLedgerStatus,
    risk_profile: PaperRiskProfilePayload,
) -> ShadowReviewPayload:
    checklist = [
        _check(
            "alpha_gates_passed",
            "Alpha 门禁通过",
            alpha_gates.alpha_ready and alpha_gates.passed_gates == alpha_gates.total_gates and alpha_gates.total_gates > 0,
            [alpha_gates.summary],
        ),
        _check(
            "alpha_forecast_ready",
            "Alpha 预测已清零",
            alpha_forecast.alpha_ready
            and alpha_forecast.status == "ready"
            and alpha_forecast.estimated_sessions_to_alpha_ready == 0,
            [alpha_forecast.summary],
        ),
        _check(
            "action_plan_shadow_review",
            "行动计划指向 Shadow 评审",
            action_plan.primary_action == "eligible_for_shadow_review",
            [action_plan.summary],
        ),
        _check(
            "event_ledger_replayable",
            "事件账本可回放",
            event_ledger.replay_ready and event_ledger.total_event_count > 0,
            [event_ledger.summary, f"total_event_count={event_ledger.total_event_count}"],
        ),
        _check(
            "execution_sample_sufficient",
            "执行样本充足",
            execution.filled_order_count >= 30 and execution.closed_trade_count >= 10,
            [
                f"filled={execution.filled_order_count}",
                f"closed={execution.closed_trade_count}",
                f"fill_rate={execution.fill_rate:.4f}",
            ],
        ),
        _check(
            "risk_gatekeeper_configured",
            "风控门禁已配置",
            risk_profile.risk_engine == "Trading Core RiskEngine"
            and risk_profile.max_order_notional > 0
            and risk_profile.max_daily_orders > 0,
            [
                f"risk_engine={risk_profile.risk_engine}",
                f"max_order_notional={risk_profile.max_order_notional}",
                f"max_daily_orders={risk_profile.max_daily_orders}",
            ],
        ),
    ]
    can_request_shadow_review = all(item.passed for item in checklist)
    status: ShadowReviewStatus = "ready_for_manual_review" if can_request_shadow_review else "blocked"
    return ShadowReviewPayload(
        status=status,
        strategy_id="deterministic_watchlist_v1",
        can_request_shadow_review=can_request_shadow_review,
        recommended_stage="shadow" if can_request_shadow_review else "paper",
        auto_promotion_enabled=False,
        checklist=checklist,
        residual_risks=_residual_risks(execution, event_ledger),
        summary=_summary(status),
    )


def _check(code: str, label: str, passed: bool, evidence: list[str]) -> ShadowReviewChecklistItem:
    return ShadowReviewChecklistItem(code=code, label=label, passed=passed, evidence=evidence)


def _residual_risks(
    execution: PaperExecutionDiagnosticsPayload,
    event_ledger: EventLedgerStatus,
) -> list[ShadowReviewResidualRisk]:
    risks = [
        ShadowReviewResidualRisk(
            code="paper_to_shadow_gap",
            severity="info",
            detail="模拟盘门禁通过只允许进入 Shadow 人工评审，不代表可以实盘交易。",
            evidence=["auto_promotion_enabled=false"],
        )
    ]
    if execution.max_daily_order_rejections > 0:
        risks.append(
            ShadowReviewResidualRisk(
                code="daily_order_limit_rejections",
                severity="medium",
                detail="历史模拟中出现过 max_daily_orders 拒单，Shadow 前需要继续观察执行容量。",
                evidence=[
                    f"max_daily_order_rejections={execution.max_daily_order_rejections}",
                    f"latest_rejection_code={execution.latest_rejection_code}",
                ],
            )
        )
    if event_ledger.warnings:
        risks.append(
            ShadowReviewResidualRisk(
                code="event_ledger_warnings",
                severity="high",
                detail="事件账本仍有警告，必须先处理再进入 Shadow 评审。",
                evidence=event_ledger.warnings,
            )
        )
    return risks


def _summary(status: ShadowReviewStatus) -> str:
    if status == "ready_for_manual_review":
        return "Shadow review packet is ready for manual review; auto promotion is disabled."
    return "Shadow review packet is blocked; continue paper validation before manual review."
