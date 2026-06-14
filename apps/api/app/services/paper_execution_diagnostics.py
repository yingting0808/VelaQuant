from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import PaperOrder, PaperOrderSide, PaperOrderStatus
from app.services.market_calendar import current_market_trading_day
from app.services.workspace import get_or_create_default_workspace


class PaperExecutionRejectionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_code: str
    count: int
    latest_reason: str | None


class PaperExecutionDiagnosticsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_count: int
    filled_order_count: int
    rejected_order_count: int
    buy_order_count: int
    sell_order_count: int
    closed_trade_count: int
    fill_rate: float
    rejection_rate: float
    realized_pnl: float
    average_realized_pnl: float
    latest_rejection_code: str | None
    max_daily_order_rejections: int
    max_daily_order_buy_rejections: int
    max_daily_order_sell_rejections: int
    rejection_reasons: list[PaperExecutionRejectionReason]
    summary: str


def get_paper_execution_diagnostics(
    session: Session,
    *,
    team_id: UUID | None = None,
    as_of_trading_day: str | None = None,
) -> PaperExecutionDiagnosticsPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    cutoff = _as_of_date(as_of_trading_day)
    orders = list(
        session.exec(
            select(PaperOrder).where(PaperOrder.team_id == team_id).order_by(PaperOrder.submitted_at.desc())
        ).all()
    )
    orders = [order for order in orders if order.submitted_at.date() <= cutoff]
    if not orders:
        return PaperExecutionDiagnosticsPayload(
            order_count=0,
            filled_order_count=0,
            rejected_order_count=0,
            buy_order_count=0,
            sell_order_count=0,
            closed_trade_count=0,
            fill_rate=0,
            rejection_rate=0,
            realized_pnl=0,
            average_realized_pnl=0,
            latest_rejection_code=None,
            max_daily_order_rejections=0,
            max_daily_order_buy_rejections=0,
            max_daily_order_sell_rejections=0,
            rejection_reasons=[],
            summary="No paper execution orders are available yet.",
        )

    filled_orders = [order for order in orders if order.status == PaperOrderStatus.filled]
    rejected_orders = [order for order in orders if order.status == PaperOrderStatus.rejected]
    buy_orders = [order for order in orders if order.side == PaperOrderSide.buy]
    sell_orders = [order for order in orders if order.side == PaperOrderSide.sell]
    closed_orders = [order for order in filled_orders if order.side == PaperOrderSide.sell]
    realized_pnl = round(sum(order.realized_pnl for order in closed_orders), 2)
    average_realized_pnl = round(realized_pnl / len(closed_orders), 2) if closed_orders else 0
    rejection_reasons = _rejection_reasons(rejected_orders)
    latest_rejection_code = _risk_code(rejected_orders[0]) if rejected_orders else None
    max_daily_order_rejections = sum(1 for order in rejected_orders if _risk_code(order) == "max_daily_orders")
    max_daily_order_buy_rejections = sum(
        1
        for order in rejected_orders
        if _risk_code(order) == "max_daily_orders" and order.side == PaperOrderSide.buy
    )
    max_daily_order_sell_rejections = sum(
        1
        for order in rejected_orders
        if _risk_code(order) == "max_daily_orders" and order.side == PaperOrderSide.sell
    )
    order_count = len(orders)
    return PaperExecutionDiagnosticsPayload(
        order_count=order_count,
        filled_order_count=len(filled_orders),
        rejected_order_count=len(rejected_orders),
        buy_order_count=len(buy_orders),
        sell_order_count=len(sell_orders),
        closed_trade_count=len(closed_orders),
        fill_rate=round(len(filled_orders) / order_count, 4),
        rejection_rate=round(len(rejected_orders) / order_count, 4),
        realized_pnl=realized_pnl,
        average_realized_pnl=average_realized_pnl,
        latest_rejection_code=latest_rejection_code,
        max_daily_order_rejections=max_daily_order_rejections,
        max_daily_order_buy_rejections=max_daily_order_buy_rejections,
        max_daily_order_sell_rejections=max_daily_order_sell_rejections,
        rejection_reasons=rejection_reasons,
        summary=_summary(len(filled_orders), len(rejected_orders), len(closed_orders), realized_pnl),
    )


def _rejection_reasons(orders: list[PaperOrder]) -> list[PaperExecutionRejectionReason]:
    grouped: dict[str, list[PaperOrder]] = {}
    for order in orders:
        grouped.setdefault(_risk_code(order), []).append(order)
    items: list[PaperExecutionRejectionReason] = []
    for risk_code, code_orders in grouped.items():
        latest = max(code_orders, key=lambda order: order.submitted_at)
        items.append(
            PaperExecutionRejectionReason(
                risk_code=risk_code,
                count=len(code_orders),
                latest_reason=latest.rejection_reason,
            )
        )
    return sorted(items, key=lambda item: max(order.submitted_at for order in grouped[item.risk_code]), reverse=True)


def _risk_code(order: PaperOrder) -> str:
    return order.risk_code or "unknown"


def _as_of_date(value: str | None) -> date:
    if value is None:
        return date.fromisoformat(current_market_trading_day())
    return date.fromisoformat(value)


def _summary(filled_count: int, rejected_count: int, closed_count: int, realized_pnl: float) -> str:
    return (
        f"Paper execution diagnostics: {filled_count} filled, {rejected_count} rejected, "
        f"{closed_count} closed trades, realized PnL {realized_pnl:.2f}."
    )
