from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload, get_alpha_gate_progress
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, get_paper_execution_diagnostics
from app.services.paper_operations import PaperOperationsStatusPayload, get_paper_operations_status
from app.services.paper_review_trend import PaperReviewTrendPayload, get_paper_review_trend
from app.services.paper_risk_limit_review import PaperRiskLimitReviewPayload, get_paper_risk_limit_review
from app.services.paper_risk_profile import PaperRiskProfilePayload, get_paper_risk_profile
from app.services.workspace import get_or_create_default_workspace


class PaperActionPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int
    action_code: str
    title: str
    detail: str
    evidence: list[str]


class PaperActionPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness: str
    primary_action: str
    items: list[PaperActionPlanItem]
    summary: str


def get_paper_action_plan(session: Session) -> PaperActionPlanPayload:
    team_id = get_or_create_default_workspace(session).team.id
    return build_paper_action_plan(
        operations=get_paper_operations_status(session, team_id=team_id),
        alpha_gates=get_alpha_gate_progress(session, team_id=team_id),
        execution=get_paper_execution_diagnostics(session, team_id=team_id),
        risk_profile=get_paper_risk_profile(session, team_id=team_id),
        risk_limit_review=get_paper_risk_limit_review(session, team_id=team_id),
        review_trend=get_paper_review_trend(session, team_id=team_id),
    )


def build_paper_action_plan(
    *,
    operations: PaperOperationsStatusPayload,
    alpha_gates: AlphaGateProgressPayload,
    execution: PaperExecutionDiagnosticsPayload,
    risk_profile: PaperRiskProfilePayload,
    risk_limit_review: PaperRiskLimitReviewPayload | None = None,
    review_trend: PaperReviewTrendPayload | None = None,
) -> PaperActionPlanPayload:
    items: list[PaperActionPlanItem] = []
    if "legacy_manual_future_runs_detected" in operations.data_quality_warnings:
        latest_day = operations.latest_legacy_manual_future_trading_day or "unknown"
        items.append(
            PaperActionPlanItem(
                priority=1,
                action_code="quarantine_legacy_manual_future_runs",
                title="标记旧运行",
                detail=(
                    f"检测到 {operations.legacy_manual_future_run_count} 条旧 manual 未来日期运行；"
                    "先标记为 simulation，避免继续污染纸面账户复盘。"
                ),
                evidence=[
                    f"legacy_manual_future_run_count={operations.legacy_manual_future_run_count}",
                    f"latest_legacy_trading_day={latest_day}",
                    operations.summary,
                ],
            )
        )

    if not operations.event_ledger_ready or "event_ledger_not_replayable" in operations.blockers:
        items.append(
            PaperActionPlanItem(
                priority=1,
                action_code="repair_event_ledger",
                title="修复事件账本",
                detail="最新纸面运行不可完整回放，先修复 CoreEventLog 再继续判断策略质量。",
                evidence=[operations.summary, f"latest_run_event_count={operations.latest_run_event_count}"],
            )
        )

    latest_review = review_trend.items[0] if review_trend is not None and review_trend.items else None
    if latest_review is not None and latest_review.daily_pnl < 0:
        items.append(
            PaperActionPlanItem(
                priority=2,
                action_code="review_negative_daily_pnl",
                title="复盘亏损日",
                detail=(
                    f"{latest_review.trading_day} 日 PnL {latest_review.daily_pnl:.2f} "
                    f"({latest_review.daily_return:.2%})；先复盘候选理由、入场价格和退出规则。"
                ),
                evidence=[
                    review_trend.summary if review_trend is not None else "",
                    f"daily_pnl={latest_review.daily_pnl:.2f}",
                    f"daily_return={latest_review.daily_return:.4f}",
                    f"latest_expectancy={review_trend.latest_expectancy:.2f}" if review_trend is not None else "",
                ],
            )
        )

    open_gates = [item for item in alpha_gates.items if not item.passed]
    closed_trade_gate = _gate(open_gates, "closed_trade_sample")
    filled_order_gate = _gate(open_gates, "filled_order_sample")
    awaiting_post_limit_sample = (
        risk_limit_review is not None and "awaiting_post_limit_sample" in risk_limit_review.blockers
    )
    can_apply_paper_risk_limit = (
        risk_limit_review is not None
        and risk_limit_review.status == "review_required"
        and risk_limit_review.recommended_paper_max_daily_orders > risk_limit_review.current_max_daily_orders
        and not risk_limit_review.live_change_allowed
    )
    if can_apply_paper_risk_limit and (closed_trade_gate is not None or filled_order_gate is not None):
        items.append(
            PaperActionPlanItem(
                priority=2,
                action_code="apply_paper_risk_limit_recommendation",
                title="应用 Paper 限额建议",
                detail=(
                    "按默认推荐提高模拟盘样本采集容量："
                    f"max_daily_orders {risk_limit_review.current_max_daily_orders} -> "
                    f"{risk_limit_review.recommended_paper_max_daily_orders}；Live 不变。"
                ),
                evidence=[
                    risk_limit_review.summary,
                    f"filled={execution.filled_order_count}",
                    f"closed={execution.closed_trade_count}",
                    f"rejected={execution.max_daily_order_rejections}",
                ],
            )
        )
    elif awaiting_post_limit_sample:
        items.append(
            PaperActionPlanItem(
                priority=2,
                action_code="collect_post_limit_sample",
                title="收集新限额样本",
                detail=(
                    f"Paper 风险限额已更新到 max_daily_orders={risk_profile.max_daily_orders}；"
                    "等待下一次真实 paper 运行后再判断是否需要继续调整。"
                ),
                evidence=[
                    risk_limit_review.summary if risk_limit_review is not None else "",
                    f"filled={execution.filled_order_count}",
                    f"closed={execution.closed_trade_count}",
                    f"rejected={execution.max_daily_order_rejections}",
                ],
            )
        )
    elif execution.max_daily_order_rejections > 0 and (closed_trade_gate is not None or filled_order_gate is not None):
        items.append(
            PaperActionPlanItem(
                priority=2,
                action_code="review_daily_order_limit",
                title="复核日订单上限",
                detail=(
                    f"执行诊断显示 {execution.max_daily_order_rejections} 笔 max_daily_orders 拒单；"
                    f"当前 max_daily_orders={risk_profile.max_daily_orders}，且成交/闭环样本仍未达标。"
                ),
                evidence=[
                    f"filled={execution.filled_order_count}",
                    f"closed={execution.closed_trade_count}",
                    f"rejected={execution.rejected_order_count}",
                ],
            )
        )

    if open_gates:
        remaining = " / ".join(f"{item.label}还差{item.remaining:g}{item.unit}" for item in open_gates)
        items.append(
            PaperActionPlanItem(
                priority=3,
                action_code="continue_paper_validation",
                title="继续纸面验证",
                detail=f"Alpha 仍在 collecting，{remaining}。",
                evidence=[alpha_gates.summary],
            )
        )

    if operations.recommended_action in {"run_daily_paper_trading", "retry_daily_paper_trading"}:
        items.append(
            PaperActionPlanItem(
                priority=4,
                action_code=operations.recommended_action,
                title="运行纸面交易链路",
                detail=operations.summary,
                evidence=[f"trading_day={operations.trading_day}", f"run_state={operations.run_state}"],
            )
        )

    if alpha_gates.alpha_ready:
        items.append(
            PaperActionPlanItem(
                priority=1,
                action_code="eligible_for_shadow_review",
                title="进入 Shadow 评审",
                detail="Alpha 门禁已通过，可以进入人工评审，不自动晋级。",
                evidence=[alpha_gates.summary],
            )
        )

    if not items:
        items.append(
            PaperActionPlanItem(
                priority=5,
                action_code="hold_until_next_session",
                title="等待下一次调度",
                detail="当前没有阻断动作，等待下一交易日继续收集样本。",
                evidence=[operations.summary],
            )
        )

    items = sorted(items, key=lambda item: item.priority)
    readiness = "alpha_ready" if alpha_gates.alpha_ready else operations.health_status
    primary_action = items[0].action_code
    return PaperActionPlanPayload(
        readiness=readiness,
        primary_action=primary_action,
        items=items,
        summary=f"Paper action plan primary action: {primary_action}; {len(items)} actions available.",
    )


def _gate(items: list[AlphaGateProgressItem], gate: str) -> AlphaGateProgressItem | None:
    for item in items:
        if item.gate == gate:
            return item
    return None
