from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.services.alpha_validation import (
    MAX_VALIDATION_DRAWDOWN,
    MIN_CLOSED_TRADES,
    MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS,
    MIN_FILLED_ORDERS,
    MIN_REVIEW_DAYS,
    AlphaValidationPayload,
    get_alpha_validation,
)


GateComparison = Literal["at_least", "greater_than", "at_most"]


class AlphaGateProgressItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate: str
    label: str
    current: float
    required: float
    remaining: float
    unit: str
    comparison: GateComparison
    passed: bool


class AlphaGateProgressPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alpha_ready: bool
    validation_level: str
    passed_gates: int
    total_gates: int
    items: list[AlphaGateProgressItem]
    summary: str


def get_alpha_gate_progress(
    session: Session,
    *,
    team_id: UUID | None = None,
    strategy_id: str = "deterministic_watchlist_v1",
) -> AlphaGateProgressPayload:
    alpha = get_alpha_validation(session, team_id=team_id, strategy_id=strategy_id)
    return build_alpha_gate_progress(alpha)


def build_alpha_gate_progress(alpha: AlphaValidationPayload) -> AlphaGateProgressPayload:
    items = [
        _at_least("review_day_sample", "复盘天数", alpha.review_day_count, MIN_REVIEW_DAYS, "天"),
        _at_least(
            "consecutive_positive_expectancy",
            "连续正期望",
            alpha.consecutive_positive_expectancy_days,
            MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS,
            "天",
        ),
        _at_least("filled_order_sample", "成交订单", alpha.filled_order_count, MIN_FILLED_ORDERS, "笔"),
        _at_least("closed_trade_sample", "闭环交易", alpha.closed_trade_count, MIN_CLOSED_TRADES, "笔"),
        _at_least("event_ledger_populated", "事件账本", alpha.event_chain_count, 1, "条"),
        _at_least("real_market_event_evidence", "真实事件证据", alpha.real_market_event_chain_count, 1, "条"),
        _at_least(
            "real_market_backtest",
            "真实历史回测",
            1 if alpha.has_real_market_backtest else 0,
            1,
            "次",
        ),
        _greater_than("latest_positive_expectancy", "最新期望", alpha.latest_expectancy, 0, "USD"),
        _greater_than("average_positive_expectancy", "平均期望", alpha.average_expectancy, 0, "USD"),
        _at_most("drawdown_limit", "最大回撤", alpha.max_drawdown, MAX_VALIDATION_DRAWDOWN, "ratio"),
        _at_most("score_pnl_inversion_review", "评分盈亏反向", alpha.score_pnl_inversion_count, 0, "项"),
    ]
    passed = sum(1 for item in items if item.passed)
    total = len(items)
    return AlphaGateProgressPayload(
        alpha_ready=alpha.alpha_ready,
        validation_level=alpha.validation_level,
        passed_gates=passed,
        total_gates=total,
        items=items,
        summary=f"Alpha gate progress: {passed}/{total} gates passed; validation level {alpha.validation_level}.",
    )


def _at_least(gate: str, label: str, current: float, required: float, unit: str) -> AlphaGateProgressItem:
    return AlphaGateProgressItem(
        gate=gate,
        label=label,
        current=round(current, 4),
        required=round(required, 4),
        remaining=round(max(0, required - current), 4),
        unit=unit,
        comparison="at_least",
        passed=current >= required,
    )


def _greater_than(gate: str, label: str, current: float, required: float, unit: str) -> AlphaGateProgressItem:
    return AlphaGateProgressItem(
        gate=gate,
        label=label,
        current=round(current, 4),
        required=round(required, 4),
        remaining=round(max(0.0, required - current + 0.01), 4) if current <= required else 0,
        unit=unit,
        comparison="greater_than",
        passed=current > required,
    )


def _at_most(gate: str, label: str, current: float, required: float, unit: str) -> AlphaGateProgressItem:
    return AlphaGateProgressItem(
        gate=gate,
        label=label,
        current=round(current, 4),
        required=round(required, 4),
        remaining=round(max(0, current - required), 4),
        unit=unit,
        comparison="at_most",
        passed=current <= required,
    )
