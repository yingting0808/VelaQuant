from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.alpha_gate_progress import AlphaGateProgressItem, AlphaGateProgressPayload, get_alpha_gate_progress
from app.services.alpha_validation_forecast import AlphaValidationForecastPayload, get_alpha_validation_forecast
from app.services.alpha_validation_snapshot import get_alpha_validation_snapshots
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, get_paper_execution_diagnostics
from app.services.paper_operations import PaperOperationsStatusPayload, get_paper_operations_status
from app.services.paper_review_trend import PaperReviewTrendPayload, get_paper_review_trend
from app.services.paper_risk_limit_review import PaperRiskLimitReviewPayload, get_paper_risk_limit_review
from app.services.paper_risk_profile import PaperRiskProfilePayload, get_paper_risk_profile
from app.services.strategy_attribution import attribute_current_paper_strategy
from app.services.workspace import get_or_create_default_workspace

if TYPE_CHECKING:
    from app.services.paper_scheduler import PaperSchedulerStatus


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
    from app.services.paper_scheduler import get_paper_scheduler_status

    team_id = get_or_create_default_workspace(session).team.id
    snapshots = get_alpha_validation_snapshots(session, team_id=team_id, limit=1)
    attribution = attribute_current_paper_strategy(session, team_id=team_id)
    return build_paper_action_plan(
        operations=get_paper_operations_status(session, team_id=team_id),
        alpha_gates=get_alpha_gate_progress(session, team_id=team_id),
        execution=get_paper_execution_diagnostics(session, team_id=team_id),
        risk_profile=get_paper_risk_profile(session, team_id=team_id),
        risk_limit_review=get_paper_risk_limit_review(session, team_id=team_id),
        review_trend=get_paper_review_trend(session, team_id=team_id),
        alpha_forecast=get_alpha_validation_forecast(session, team_id=team_id),
        scheduler=get_paper_scheduler_status(),
        latest_alpha_snapshot_trading_day=snapshots.latest.trading_day if snapshots.latest is not None else None,
        inverted_score_pnl_tickers=[
            item.ticker for item in attribution.ticker_diagnostics if item.score_pnl_alignment == "inverted"
        ],
    )


def build_paper_action_plan(
    *,
    operations: PaperOperationsStatusPayload,
    alpha_gates: AlphaGateProgressPayload,
    execution: PaperExecutionDiagnosticsPayload,
    risk_profile: PaperRiskProfilePayload,
    risk_limit_review: PaperRiskLimitReviewPayload | None = None,
    review_trend: PaperReviewTrendPayload | None = None,
    alpha_forecast: AlphaValidationForecastPayload | None = None,
    scheduler: PaperSchedulerStatus | None = None,
    latest_alpha_snapshot_trading_day: str | None = None,
    inverted_score_pnl_tickers: list[str] | None = None,
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

    if "event_ledger_not_replayable" in operations.blockers:
        items.append(
            PaperActionPlanItem(
                priority=1,
                action_code="repair_event_ledger",
                title="修复事件账本",
                detail="最新纸面运行不可完整回放，先修复 CoreEventLog 再继续判断策略质量。",
                evidence=[operations.summary, f"latest_run_event_count={operations.latest_run_event_count}"],
            )
        )

    open_gates = [item for item in alpha_gates.items if not item.passed]
    score_pnl_gate = _gate(open_gates, "score_pnl_inversion_review")
    if score_pnl_gate is not None:
        tickers = sorted(inverted_score_pnl_tickers or [])
        ticker_text = ", ".join(tickers) if tickers else f"{score_pnl_gate.remaining:g} 项"
        items.append(
            PaperActionPlanItem(
                priority=2,
                action_code="review_score_pnl_inversion",
                title="复盘评分背离",
                detail=(
                    f"检测到 {ticker_text} 的候选评分方向与观测盈亏相反；"
                    "先复盘候选评分权重、证据方向和退出规则，暂不把该信号视为可验证 Alpha。"
                ),
                evidence=[
                    alpha_gates.summary,
                    f"score_pnl_inversion_remaining={score_pnl_gate.remaining:g}",
                    f"inverted_tickers={','.join(tickers) if tickers else 'unknown'}",
                ],
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
    elif (
        risk_limit_review is None
        and execution.max_daily_order_rejections > 0
        and (closed_trade_gate is not None or filled_order_gate is not None)
    ):
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

    if open_gates and latest_alpha_snapshot_trading_day == operations.trading_day:
        items.append(
            PaperActionPlanItem(
                priority=5,
                action_code="hold_until_next_session",
                title="等待下一次调度",
                detail=_hold_until_next_session_detail(alpha_forecast, scheduler),
                evidence=[
                    alpha_gates.summary,
                    f"latest_alpha_snapshot_trading_day={latest_alpha_snapshot_trading_day}",
                    operations.summary,
                    *_hold_until_next_session_evidence(alpha_forecast, scheduler),
                ],
            )
        )
    elif open_gates:
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


def _hold_until_next_session_detail(
    alpha_forecast: AlphaValidationForecastPayload | None,
    scheduler: PaperSchedulerStatus | None,
) -> str:
    detail = "当前交易日 Alpha 验证快照已记录，等待下一交易日继续收集样本。"
    parts: list[str] = []
    if alpha_forecast is not None and alpha_forecast.estimated_sessions_to_alpha_ready is not None:
        parts.append(f"预计还需 {alpha_forecast.estimated_sessions_to_alpha_ready} 次有效 paper sessions")
    if scheduler is not None and scheduler.next_actionable_run_at is not None:
        parts.append(
            "下一次有效采样 "
            f"{scheduler.next_actionable_run_at.isoformat()}，交易日 {scheduler.next_actionable_trading_day or '未知'}"
        )
    if not parts:
        return detail
    return f"{detail}{'；'.join(parts)}。"


def _hold_until_next_session_evidence(
    alpha_forecast: AlphaValidationForecastPayload | None,
    scheduler: PaperSchedulerStatus | None,
) -> list[str]:
    evidence: list[str] = []
    if alpha_forecast is not None:
        evidence.append(alpha_forecast.summary)
        if alpha_forecast.estimated_sessions_to_alpha_ready is not None:
            evidence.append(f"estimated_sessions_to_alpha_ready={alpha_forecast.estimated_sessions_to_alpha_ready}")
        if alpha_forecast.limiting_gate is not None:
            evidence.append(f"limiting_gate={alpha_forecast.limiting_gate}")
    if scheduler is not None:
        if scheduler.next_actionable_run_at is not None:
            evidence.append(f"next_actionable_run_at={scheduler.next_actionable_run_at.isoformat()}")
        if scheduler.next_actionable_trading_day is not None:
            evidence.append(f"next_actionable_trading_day={scheduler.next_actionable_trading_day}")
        if scheduler.next_actionable_execution_gate is not None:
            evidence.append(f"next_actionable_execution_gate={scheduler.next_actionable_execution_gate}")
    return evidence
