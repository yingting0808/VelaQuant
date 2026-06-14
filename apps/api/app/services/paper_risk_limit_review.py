import json
from math import ceil
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperOrder, PaperOrderSide, PaperOrderStatus, PaperRun, PaperRunStatus, utc_now
from app.services.alpha_gate_progress import AlphaGateProgressPayload, get_alpha_gate_progress
from app.services.paper_execution_diagnostics import PaperExecutionDiagnosticsPayload, get_paper_execution_diagnostics
from app.services.paper_risk_profile import PaperRiskProfilePayload, get_paper_risk_profile
from app.services.paper_risk_settings import get_active_paper_risk_setting
from app.services.workspace import get_or_create_default_workspace


PaperRiskLimitReviewStatus = Literal["hold", "review_required"]


class PaperRiskLimitReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PaperRiskLimitReviewStatus
    current_max_daily_orders: int
    recommended_paper_max_daily_orders: int
    live_change_allowed: bool
    max_daily_order_rejections: int
    max_daily_order_buy_rejections: int
    max_daily_order_sell_rejections: int
    filled_order_count: int
    closed_trade_count: int
    sample_collection_blocked: bool
    blockers: list[str]
    summary: str


def get_paper_risk_limit_review(session: Session, *, team_id: UUID | None = None) -> PaperRiskLimitReviewPayload:
    resolved_team_id = team_id or get_or_create_default_workspace(session).team.id
    review = build_paper_risk_limit_review(
        execution=get_paper_execution_diagnostics(session, team_id=resolved_team_id),
        risk_profile=get_paper_risk_profile(session, team_id=resolved_team_id),
        alpha_gates=get_alpha_gate_progress(session, team_id=resolved_team_id),
    )
    setting = get_active_paper_risk_setting(session, team_id=resolved_team_id)
    if (
        setting is not None
        and review.status == "review_required"
        and not _has_buy_daily_order_rejection_after(session, team_id=resolved_team_id, since=setting.updated_at)
    ):
        if _has_completed_run_after(session, team_id=resolved_team_id, since=setting.updated_at):
            return review.model_copy(
                update={
                    "status": "hold",
                    "recommended_paper_max_daily_orders": review.current_max_daily_orders,
                    "sample_collection_blocked": False,
                    "blockers": [],
                    "summary": (
                        "Paper risk limit review: hold max_daily_orders at "
                        f"{review.current_max_daily_orders}; latest post-limit sample completed without a new "
                        "buy max_daily_orders rejection."
                    ),
                }
            )
        return review.model_copy(
            update={
                "status": "hold",
                "recommended_paper_max_daily_orders": review.current_max_daily_orders,
                "sample_collection_blocked": False,
                "blockers": ["awaiting_post_limit_sample"],
                "summary": (
                    "Paper risk limit review: hold max_daily_orders at "
                    f"{review.current_max_daily_orders}; awaiting new paper sample after the latest paper-only "
                    "risk limit update."
                ),
            }
        )
    return review


def build_paper_risk_limit_review(
    *,
    execution: PaperExecutionDiagnosticsPayload,
    risk_profile: PaperRiskProfilePayload,
    alpha_gates: AlphaGateProgressPayload,
) -> PaperRiskLimitReviewPayload:
    sample_blockers = [
        item.gate
        for item in alpha_gates.items
        if not item.passed and item.gate in {"filled_order_sample", "closed_trade_sample"}
    ]
    has_buy_daily_order_pressure = execution.max_daily_order_buy_rejections > 0
    has_sell_exit_daily_order_pressure = (
        execution.max_daily_order_buy_rejections == 0 and execution.max_daily_order_sell_rejections > 0
    )
    sample_collection_blocked = has_buy_daily_order_pressure and bool(sample_blockers)
    blockers = [*sample_blockers]
    if has_buy_daily_order_pressure:
        blockers.append("max_daily_orders")
    elif has_sell_exit_daily_order_pressure:
        blockers = ["max_daily_orders_sell_exit_rejections"]

    if sample_collection_blocked:
        recommended = _recommended_paper_limit(
            current=risk_profile.max_daily_orders,
            rejected=execution.max_daily_order_buy_rejections,
        )
        status: PaperRiskLimitReviewStatus = "review_required"
    else:
        recommended = risk_profile.max_daily_orders
        status = "hold"

    return PaperRiskLimitReviewPayload(
        status=status,
        current_max_daily_orders=risk_profile.max_daily_orders,
        recommended_paper_max_daily_orders=recommended,
        live_change_allowed=False,
        max_daily_order_rejections=execution.max_daily_order_rejections,
        max_daily_order_buy_rejections=execution.max_daily_order_buy_rejections,
        max_daily_order_sell_rejections=execution.max_daily_order_sell_rejections,
        filled_order_count=execution.filled_order_count,
        closed_trade_count=execution.closed_trade_count,
        sample_collection_blocked=sample_collection_blocked,
        blockers=blockers,
        summary=_summary(
            status=status,
            current=risk_profile.max_daily_orders,
            recommended=recommended,
            buy_rejected=execution.max_daily_order_buy_rejections,
            sell_rejected=execution.max_daily_order_sell_rejections,
            blockers=blockers,
        ),
    )


def _recommended_paper_limit(*, current: int, rejected: int) -> int:
    increment = max(1, min(5, ceil(rejected / 10)))
    return min(current * 2, current + increment)


def _has_buy_daily_order_rejection_after(session: Session, *, team_id: UUID, since) -> bool:
    as_of = utc_now().date()
    orders = session.exec(
        select(PaperOrder)
        .where(PaperOrder.team_id == team_id)
        .where(PaperOrder.side == PaperOrderSide.buy)
        .where(PaperOrder.status == PaperOrderStatus.rejected)
        .where(PaperOrder.risk_code == "max_daily_orders")
        .where(PaperOrder.submitted_at > since)
    ).all()
    if any(order.submitted_at.date() <= as_of for order in orders):
        return True

    runs = session.exec(
        select(PaperRun)
        .where(PaperRun.team_id == team_id)
        .where(PaperRun.status == PaperRunStatus.completed)
        .where(PaperRun.finished_at.is_not(None))
        .where(PaperRun.finished_at > since)
    ).all()
    return any(_run_has_buy_daily_order_rejection(session, run.id) for run in runs)


def _has_completed_run_after(session: Session, *, team_id: UUID, since) -> bool:
    return (
        session.exec(
            select(PaperRun.id)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.status == PaperRunStatus.completed)
            .where(PaperRun.finished_at.is_not(None))
            .where(PaperRun.finished_at > since)
        ).first()
        is not None
    )


def _run_has_buy_daily_order_rejection(session: Session, run_id: UUID) -> bool:
    events = session.exec(
        select(CoreEventLog)
        .where(CoreEventLog.run_id == run_id)
        .where(CoreEventLog.topic.in_(["trade_intent", "risk_decision"]))
    ).all()
    buy_correlations: set[str] = set()
    daily_limit_rejections: set[str] = set()
    for event in events:
        payload = _json_payload(event.payload_json)
        if event.topic == "trade_intent" and payload.get("side") == PaperOrderSide.buy.value:
            buy_correlations.add(event.correlation_id)
        if (
            event.topic == "risk_decision"
            and payload.get("status") == "rejected"
            and payload.get("code") == "max_daily_orders"
        ):
            daily_limit_rejections.add(event.correlation_id)
    return bool(buy_correlations & daily_limit_rejections)


def _json_payload(value: str) -> dict:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(
    *,
    status: PaperRiskLimitReviewStatus,
    current: int,
    recommended: int,
    buy_rejected: int,
    sell_rejected: int,
    blockers: list[str],
) -> str:
    if status == "hold":
        return f"Paper risk limit review: hold max_daily_orders at {current}; no paper-only capacity change is recommended."
    return (
        "Paper risk limit review: paper-only review required; "
        f"max_daily_orders {current} -> {recommended}, buy rejected {buy_rejected}, sell exit rejected {sell_rejected}; "
        f"blockers: {', '.join(blockers)}. Live limits are unchanged."
    )
