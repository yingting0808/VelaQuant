from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.data.providers.base import MarketDataProvider
from app.services.paper_action_plan import get_paper_action_plan
from app.services.paper_operations import (
    quarantine_legacy_manual_future_runs,
    repair_paper_operations_event_ledger,
)
from app.services.paper_risk_settings import apply_paper_risk_limit_recommendation
from app.services.paper_trading import run_daily_paper_trading_loop


class PaperActionExecutionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executed: bool
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

    if action == "apply_paper_risk_limit_recommendation":
        result = apply_paper_risk_limit_recommendation(session).model_dump(mode="json")
    elif action == "repair_event_ledger":
        result = repair_paper_operations_event_ledger(session).model_dump(mode="json")
    elif action == "quarantine_legacy_manual_future_runs":
        result = quarantine_legacy_manual_future_runs(session).model_dump(mode="json")
    elif action in {"run_daily_paper_trading", "retry_daily_paper_trading"}:
        result = run_daily_paper_trading_loop(session, provider).model_dump(mode="json")
    else:
        executed = False

    next_plan = get_paper_action_plan(session)
    verb = "Executed" if executed else "No executable default for"
    return PaperActionExecutionPayload(
        executed=executed,
        action_code=action,
        next_primary_action=next_plan.primary_action,
        result=result,
        summary=f"{verb} primary action {action}; next action {next_plan.primary_action}.",
    )
