from datetime import datetime, timezone
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskDecision, RiskDecisionStatus, RiskEngine
from app.trading_core.strategy import TradeIntent


class OrderState(str, Enum):
    new = "new"
    validated = "validated"
    risk_approved = "risk_approved"
    sent = "sent"
    partial_fill = "partial_fill"
    filled = "filled"
    rejected = "rejected"
    position_open = "position_open"
    position_closing = "position_closing"
    closed = "closed"


class OrderStateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: OrderState
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""


class ExecutionReportStatus(str, Enum):
    partial_fill = "partial_fill"
    filled = "filled"
    rejected = "rejected"


class ExecutionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionReportStatus
    broker_order_id: str | None = None
    average_fill_price: float | None = Field(default=None, gt=0)
    message: str = ""


class CoreOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: UUID = Field(default_factory=uuid4)
    intent: TradeIntent
    current_state: OrderState = OrderState.new
    state_history: list[OrderStateRecord] = Field(
        default_factory=lambda: [OrderStateRecord(state=OrderState.new, reason="Order created.")]
    )
    risk_decision: RiskDecision | None = None
    broker_order_id: str | None = None
    average_fill_price: float | None = None

    def transition(self, state: OrderState, reason: str = "") -> None:
        if self.current_state in {OrderState.filled, OrderState.rejected, OrderState.closed}:
            raise ValueError(f"Cannot transition terminal order {self.order_id} from {self.current_state}.")
        self.current_state = state
        self.state_history.append(OrderStateRecord(state=state, reason=reason))


class ExecutionAdapter(Protocol):
    def submit_order(self, order: CoreOrder, portfolio: PortfolioState) -> ExecutionReport:
        ...


class MockExecutionAdapter:
    def submit_order(self, order: CoreOrder, portfolio: PortfolioState) -> ExecutionReport:
        return ExecutionReport(
            status=ExecutionReportStatus.filled,
            broker_order_id=f"MOCK-{order.order_id}",
            message="Synchronously filled by mock execution adapter.",
        )


class ExecutionEngine:
    def __init__(self, risk_engine: RiskEngine, adapter: ExecutionAdapter | None = None) -> None:
        self.risk_engine = risk_engine
        self.adapter = adapter or MockExecutionAdapter()

    def submit_intent(self, intent: TradeIntent, portfolio: PortfolioState) -> CoreOrder:
        order = CoreOrder(intent=intent)
        order.transition(OrderState.validated, "Intent passed execution payload validation.")
        decision = self.risk_engine.evaluate(intent, portfolio)
        order.risk_decision = decision

        if decision.status == RiskDecisionStatus.rejected:
            order.transition(OrderState.rejected, decision.reason)
            return order

        order.transition(OrderState.risk_approved, decision.reason)
        order.transition(OrderState.sent, "Sent to execution adapter.")
        report = self.adapter.submit_order(order, portfolio)
        order.broker_order_id = report.broker_order_id
        order.average_fill_price = report.average_fill_price
        if report.status == ExecutionReportStatus.rejected:
            order.transition(OrderState.rejected, report.message)
        elif report.status == ExecutionReportStatus.partial_fill:
            order.transition(OrderState.partial_fill, report.message)
        else:
            order.transition(OrderState.filled, report.message)
        return order
