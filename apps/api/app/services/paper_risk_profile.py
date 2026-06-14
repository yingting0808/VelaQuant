from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.paper_trading import (
    DEFAULT_EXIT_STOP_LOSS_PCT,
    DEFAULT_EXIT_TAKE_PROFIT_PCT,
)
from app.services.paper_risk_settings import get_paper_risk_limits
from app.services.workspace import get_or_create_default_workspace


class PaperRiskProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_engine: str
    max_order_notional: float
    max_position_weight: float
    max_daily_orders: int
    exit_take_profit_pct: float
    exit_stop_loss_pct: float
    summary: str


def get_paper_risk_profile(session: Session | None = None, *, team_id=None) -> PaperRiskProfilePayload:
    resolved_team_id = team_id
    if session is not None and resolved_team_id is None:
        resolved_team_id = get_or_create_default_workspace(session).team.id
    limits = get_paper_risk_limits(session, team_id=resolved_team_id)
    return PaperRiskProfilePayload(
        risk_engine="Trading Core RiskEngine",
        max_order_notional=limits.max_order_notional,
        max_position_weight=limits.max_position_weight,
        max_daily_orders=limits.max_daily_orders,
        exit_take_profit_pct=DEFAULT_EXIT_TAKE_PROFIT_PCT,
        exit_stop_loss_pct=DEFAULT_EXIT_STOP_LOSS_PCT,
        summary=(
            "Paper risk profile: max_order_notional "
            f"{limits.max_order_notional:.2f}, max_position_weight {limits.max_position_weight:.2%}, "
            f"max_daily_orders {limits.max_daily_orders}, exits at "
            f"{DEFAULT_EXIT_TAKE_PROFIT_PCT:.2%} / {DEFAULT_EXIT_STOP_LOSS_PCT:.2%}."
        ),
    )
