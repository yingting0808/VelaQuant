from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.trading_core.portfolio import PortfolioState
from app.trading_core.strategy import TradeIntent, TradeIntentSide


class RiskDecisionStatus(str, Enum):
    approved = "approved"
    rejected = "rejected"


class RiskDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RiskDecisionStatus
    code: str
    reason: str


class RiskLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_order_notional: float = Field(default=2000, gt=0)
    max_position_weight: float = Field(default=0.1, gt=0, le=1)
    max_daily_orders: int = Field(default=5, ge=1)


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def can_trade(self, intent: TradeIntent, portfolio: PortfolioState) -> RiskDecision:
        if intent.notional > self.limits.max_order_notional:
            return RiskDecision(
                status=RiskDecisionStatus.rejected,
                code="max_order_notional",
                reason=f"Order notional {intent.notional:.2f} exceeds limit {self.limits.max_order_notional:.2f}.",
            )
        if intent.side == TradeIntentSide.buy and intent.notional > portfolio.cash:
            return RiskDecision(
                status=RiskDecisionStatus.rejected,
                code="insufficient_cash",
                reason=f"Order notional {intent.notional:.2f} exceeds cash {portfolio.cash:.2f}.",
            )
        if intent.side == TradeIntentSide.sell and intent.notional > portfolio.position_value(intent.ticker):
            return RiskDecision(
                status=RiskDecisionStatus.rejected,
                code="insufficient_position_value",
                reason=(
                    f"Sell notional {intent.notional:.2f} exceeds current position value "
                    f"{portfolio.position_value(intent.ticker):.2f}."
                ),
            )
        return RiskDecision(status=RiskDecisionStatus.approved, code="can_trade", reason="Trade passed basic checks.")

    def can_open_position(self, intent: TradeIntent, portfolio: PortfolioState) -> RiskDecision:
        if intent.side == TradeIntentSide.sell or portfolio.has_position(intent.ticker):
            return RiskDecision(status=RiskDecisionStatus.approved, code="position_exists", reason="Position open check passed.")
        return self._check_weight(intent, portfolio)

    def can_increase_position(self, intent: TradeIntent, portfolio: PortfolioState) -> RiskDecision:
        if intent.side == TradeIntentSide.sell:
            return RiskDecision(status=RiskDecisionStatus.approved, code="not_increasing", reason="Sell intent does not increase exposure.")
        return self._check_weight(intent, portfolio)

    def can_trade_today(self, portfolio: PortfolioState) -> RiskDecision:
        if portfolio.orders_today >= self.limits.max_daily_orders:
            return RiskDecision(
                status=RiskDecisionStatus.rejected,
                code="max_daily_orders",
                reason=f"Orders today {portfolio.orders_today} reached limit {self.limits.max_daily_orders}.",
            )
        return RiskDecision(status=RiskDecisionStatus.approved, code="daily_limit", reason="Daily order limit passed.")

    def evaluate(self, intent: TradeIntent, portfolio: PortfolioState) -> RiskDecision:
        checks = [
            self.can_trade_today(portfolio),
            self.can_trade(intent, portfolio),
            self.can_open_position(intent, portfolio),
            self.can_increase_position(intent, portfolio),
        ]
        for decision in checks:
            if decision.status == RiskDecisionStatus.rejected:
                return decision
        return RiskDecision(status=RiskDecisionStatus.approved, code="approved", reason="Risk engine approved intent.")

    def _check_weight(self, intent: TradeIntent, portfolio: PortfolioState) -> RiskDecision:
        projected_value = portfolio.position_value(intent.ticker) + (intent.notional if intent.side == TradeIntentSide.buy else 0)
        projected_weight = projected_value / portfolio.equity
        if projected_weight > self.limits.max_position_weight:
            return RiskDecision(
                status=RiskDecisionStatus.rejected,
                code="max_position_weight",
                reason=(
                    f"Projected weight {projected_weight:.4f} exceeds limit "
                    f"{self.limits.max_position_weight:.4f} for {intent.ticker}."
                ),
            )
        return RiskDecision(status=RiskDecisionStatus.approved, code="position_weight", reason="Position weight check passed.")
