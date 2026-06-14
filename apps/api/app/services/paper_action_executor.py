from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.core.config import get_settings
from app.data.providers.base import MarketDataProvider
from app.data.providers.registry import build_market_data_provider
from app.db.session import engine
from app.services.alpha_validation_snapshot import record_alpha_validation_snapshot
from app.services.paper_action_plan import get_paper_action_plan
from app.services.paper_operations import (
    quarantine_legacy_manual_future_runs,
    repair_paper_operations_event_ledger,
)
from app.services.paper_risk_settings import apply_paper_risk_limit_recommendation
from app.services.paper_scheduler import get_paper_scheduler_status
from app.services.paper_trading import run_daily_paper_trading_loop

BACKGROUND_PAPER_ACTIONS = {"run_daily_paper_trading", "retry_daily_paper_trading", "collect_post_limit_sample"}


class BackgroundTaskQueue(Protocol):
    def add_task(self, func, *args, **kwargs) -> None: ...


class PaperActionExecutionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executed: bool
    queued: bool = False
    status: str = "completed"
    action_code: str
    next_primary_action: str
    result: dict[str, Any] | None
    summary: str


def execute_paper_primary_action(
    session: Session,
    provider: MarketDataProvider,
) -> PaperActionExecutionPayload:
    plan = get_paper_action_plan(session)
    action = plan.primary_action
    result: dict[str, Any] | None = None
    executed = True
    status = "completed"

    if action == "apply_paper_risk_limit_recommendation":
        result = apply_paper_risk_limit_recommendation(session).model_dump(mode="json")
    elif action == "repair_event_ledger":
        result = repair_paper_operations_event_ledger(session).model_dump(mode="json")
    elif action == "quarantine_legacy_manual_future_runs":
        result = quarantine_legacy_manual_future_runs(session).model_dump(mode="json")
    elif action == "continue_paper_validation":
        result = record_alpha_validation_snapshot(session).model_dump(mode="json")
    elif action == "hold_until_next_session":
        executed = False
        status = "waiting"
        scheduler = get_paper_scheduler_status().model_dump(mode="json")
        hold_detail = plan.items[0].detail if plan.items else "Waiting for the next scheduled paper run."
        result = {"reason": hold_detail, "scheduler": scheduler}
    elif action == "review_score_pnl_inversion":
        executed = False
        status = "review_required"
        review_item = next((item for item in plan.items if item.action_code == action), None)
        result = {
            "title": review_item.title if review_item is not None else "复盘评分背离",
            "detail": review_item.detail if review_item is not None else "评分方向与观测盈亏存在反向，需要人工复盘。",
            "evidence": review_item.evidence if review_item is not None else [],
        }
    elif action in BACKGROUND_PAPER_ACTIONS:
        result = run_daily_paper_trading_loop(
            session,
            provider,
            force_new_sample=action == "collect_post_limit_sample",
        ).model_dump(mode="json")
    else:
        executed = False
        status = "skipped"

    next_plan = get_paper_action_plan(session)
    if status == "waiting":
        verb = "Holding"
    elif status == "review_required":
        verb = "Marked"
    else:
        verb = "Executed" if executed else "No executable default for"
    suffix = " waiting for the next scheduled paper run" if status == "waiting" else ""
    if status == "review_required":
        suffix = " manual review required"
    return PaperActionExecutionPayload(
        executed=executed,
        status=status,
        action_code=action,
        next_primary_action=next_plan.primary_action,
        result=result,
        summary=f"{verb} primary action {action}; next action {next_plan.primary_action}.{suffix}",
    )


def should_queue_paper_primary_action(action_code: str) -> bool:
    return action_code in BACKGROUND_PAPER_ACTIONS


def queue_paper_primary_action(
    session: Session,
    background_tasks: BackgroundTaskQueue,
) -> PaperActionExecutionPayload:
    plan = get_paper_action_plan(session)
    action = plan.primary_action
    if not should_queue_paper_primary_action(action):
        return PaperActionExecutionPayload(
            executed=False,
            queued=False,
            status="skipped",
            action_code=action,
            next_primary_action=action,
            result=None,
            summary=f"Primary action {action} is not a background paper run action.",
        )

    background_tasks.add_task(_execute_queued_paper_primary_action, action)
    return PaperActionExecutionPayload(
        executed=False,
        queued=True,
        status="queued",
        action_code=action,
        next_primary_action=action,
        result={"status_url": "/api/mvp/paper-trading/runs"},
        summary=f"Queued primary action {action}; check paper runs for completion status.",
    )


def _execute_queued_paper_primary_action(action_code: str) -> None:
    if action_code not in BACKGROUND_PAPER_ACTIONS:
        return

    settings = get_settings()
    provider = build_market_data_provider(settings)
    try:
        with Session(engine) as session:
            run_daily_paper_trading_loop(
                session,
                provider,
                force_new_sample=action_code == "collect_post_limit_sample",
            )
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()
