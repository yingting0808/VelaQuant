from math import ceil
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


AlphaValidationForecastStatus = Literal["ready", "forecastable", "blocked"]


class AlphaValidationForecastItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate: str
    label: str
    current: float
    required: float
    remaining: float
    unit: str
    passed: bool
    estimated_per_session: float | None
    estimated_sessions: int | None
    reason: str


class AlphaValidationForecastPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alpha_ready: bool
    status: AlphaValidationForecastStatus
    estimated_sessions_to_alpha_ready: int | None
    limiting_gate: str | None
    items: list[AlphaValidationForecastItem]
    summary: str


def get_alpha_validation_forecast(
    session: Session,
    *,
    team_id: UUID | None = None,
    strategy_id: str = "deterministic_watchlist_v1",
) -> AlphaValidationForecastPayload:
    alpha = get_alpha_validation(session, team_id=team_id, strategy_id=strategy_id)
    return build_alpha_validation_forecast(alpha)


def build_alpha_validation_forecast(alpha: AlphaValidationPayload) -> AlphaValidationForecastPayload:
    items = [
        _sample_gate("review_day_sample", "复盘天数", alpha.review_day_count, MIN_REVIEW_DAYS, "天", 1),
        _consecutive_positive_gate(alpha),
        _sample_gate(
            "filled_order_sample",
            "成交订单",
            alpha.filled_order_count,
            MIN_FILLED_ORDERS,
            "笔",
            _rate(alpha.filled_order_count, alpha.review_day_count),
        ),
        _sample_gate(
            "closed_trade_sample",
            "闭环交易",
            alpha.closed_trade_count,
            MIN_CLOSED_TRADES,
            "笔",
            _rate(alpha.closed_trade_count, alpha.review_day_count),
        ),
        _sample_gate("event_ledger_populated", "事件账本", alpha.event_chain_count, 1, "条", 1),
        _real_market_backtest_gate(alpha),
        _quality_gate(
            "latest_positive_expectancy",
            "最新期望",
            alpha.latest_expectancy,
            0,
            "USD",
            passed=alpha.latest_expectancy > 0,
        ),
        _quality_gate(
            "average_positive_expectancy",
            "平均期望",
            alpha.average_expectancy,
            0,
            "USD",
            passed=alpha.average_expectancy > 0,
        ),
        _drawdown_gate(alpha.max_drawdown),
    ]
    open_items = [item for item in items if not item.passed]
    if alpha.alpha_ready:
        return AlphaValidationForecastPayload(
            alpha_ready=True,
            status="ready",
            estimated_sessions_to_alpha_ready=0,
            limiting_gate=None,
            items=items,
            summary="Alpha validation already passes all paper gates.",
        )

    unforecastable = [item for item in open_items if item.estimated_sessions is None]
    if unforecastable:
        limiting_gate = unforecastable[0].gate
        return AlphaValidationForecastPayload(
            alpha_ready=False,
            status="blocked",
            estimated_sessions_to_alpha_ready=None,
            limiting_gate=limiting_gate,
            items=items,
            summary=f"Alpha validation has quality blockers that cannot be cleared by sample count alone: {limiting_gate}.",
        )

    estimated_sessions = max((item.estimated_sessions or 0 for item in open_items), default=0)
    limiting_gate = _limiting_gate(open_items)
    return AlphaValidationForecastPayload(
        alpha_ready=False,
        status="forecastable",
        estimated_sessions_to_alpha_ready=estimated_sessions,
        limiting_gate=limiting_gate,
        items=items,
        summary=f"Alpha validation needs about {estimated_sessions} more paper sessions if current sample rates continue.",
    )


def _sample_gate(
    gate: str,
    label: str,
    current: float,
    required: float,
    unit: str,
    estimated_per_session: float | None,
) -> AlphaValidationForecastItem:
    passed = current >= required
    remaining = round(max(0, required - current), 4)
    estimated_sessions = _estimated_sessions(remaining, estimated_per_session) if not passed else 0
    if passed:
        reason = "门禁已通过。"
    elif estimated_sessions is None:
        reason = "缺少足够历史样本，暂时不能估算。"
    else:
        reason = "按当前样本速度估算。"
    return AlphaValidationForecastItem(
        gate=gate,
        label=label,
        current=round(current, 4),
        required=round(required, 4),
        remaining=remaining,
        unit=unit,
        passed=passed,
        estimated_per_session=round(estimated_per_session, 4) if estimated_per_session is not None else None,
        estimated_sessions=estimated_sessions,
        reason=reason,
    )


def _consecutive_positive_gate(alpha: AlphaValidationPayload) -> AlphaValidationForecastItem:
    passed = alpha.consecutive_positive_expectancy_days >= MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS
    remaining = round(max(0, MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS - alpha.consecutive_positive_expectancy_days), 4)
    if passed:
        estimated_sessions = 0
        reason = "门禁已通过。"
    elif alpha.latest_expectancy > 0:
        estimated_sessions = int(remaining)
        reason = "最新期望为正，按连续正期望天数推进估算。"
    else:
        estimated_sessions = None
        reason = "最新期望不为正，连续性需要先恢复。"
    return AlphaValidationForecastItem(
        gate="consecutive_positive_expectancy",
        label="连续正期望",
        current=alpha.consecutive_positive_expectancy_days,
        required=MIN_CONSECUTIVE_POSITIVE_EXPECTANCY_DAYS,
        remaining=remaining,
        unit="天",
        passed=passed,
        estimated_per_session=1 if alpha.latest_expectancy > 0 else None,
        estimated_sessions=estimated_sessions,
        reason=reason,
    )


def _quality_gate(
    gate: str,
    label: str,
    current: float,
    required: float,
    unit: str,
    *,
    passed: bool,
) -> AlphaValidationForecastItem:
    return AlphaValidationForecastItem(
        gate=gate,
        label=label,
        current=round(current, 4),
        required=round(required, 4),
        remaining=0 if passed else 0.01,
        unit=unit,
        passed=passed,
        estimated_per_session=0 if passed else None,
        estimated_sessions=0 if passed else None,
        reason="门禁已通过。" if passed else "质量门禁需要真实收益改善，不能仅按样本速度估算。",
    )


def _real_market_backtest_gate(alpha: AlphaValidationPayload) -> AlphaValidationForecastItem:
    passed = alpha.has_real_market_backtest
    return AlphaValidationForecastItem(
        gate="real_market_backtest",
        label="真实历史回测",
        current=1 if passed else 0,
        required=1,
        remaining=0 if passed else 1,
        unit="次",
        passed=passed,
        estimated_per_session=0 if passed else None,
        estimated_sessions=0 if passed else None,
        reason="门禁已通过。" if passed else "需要同策略真实历史回测结果，不能仅靠模拟盘样本估算。",
    )


def _drawdown_gate(current: float) -> AlphaValidationForecastItem:
    passed = current <= MAX_VALIDATION_DRAWDOWN
    return AlphaValidationForecastItem(
        gate="drawdown_limit",
        label="最大回撤",
        current=round(current, 4),
        required=MAX_VALIDATION_DRAWDOWN,
        remaining=round(max(0, current - MAX_VALIDATION_DRAWDOWN), 4),
        unit="ratio",
        passed=passed,
        estimated_per_session=0 if passed else None,
        estimated_sessions=0 if passed else None,
        reason="门禁已通过。" if passed else "回撤门禁需要风险和收益路径改善，不能仅按样本速度估算。",
    )


def _rate(count: int, review_day_count: int) -> float | None:
    if review_day_count <= 0 or count <= 0:
        return None
    return count / review_day_count


def _estimated_sessions(remaining: float, estimated_per_session: float | None) -> int | None:
    if remaining <= 0:
        return 0
    if estimated_per_session is None or estimated_per_session <= 0:
        return None
    return ceil(remaining / estimated_per_session)


def _limiting_gate(items: list[AlphaValidationForecastItem]) -> str | None:
    if not items:
        return None
    return max(items, key=lambda item: item.estimated_sessions or 0).gate
