import json
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperOrder, PaperOrderSide, PaperOrderStatus, PaperPosition, PaperReview
from app.services.strategy_evaluation import DEFAULT_STRATEGY_ID, DEFAULT_STRATEGY_NAME
from app.services.workspace import get_or_create_default_workspace


class SignalQualityAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_event_count: int
    trade_intent_count: int
    actionable_signal_rate: float
    average_confidence: float
    false_positive_rate: float


class ExpectancyDecomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    realized_pnl: float
    unrealized_pnl: float
    closed_trade_component: float
    open_trade_component: float
    total_observed_pnl: float


class MarketRegimeAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regime: Literal["insufficient_data", "drawdown_pressure", "uptrend_capture", "range_bound"]
    basis: str
    review_count: int
    equity_change: float


class DrawdownAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["insufficient_data", "open_position_pressure", "closed_trade_losses", "equity_curve_pressure"]
    max_drawdown: float
    basis: str


class StrategyAttributionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    strategy_name: str
    signal_quality: SignalQualityAttribution
    expectancy_decomposition: ExpectancyDecomposition
    regime: MarketRegimeAttribution
    drawdown: DrawdownAttribution
    data_quality_warnings: list[str]
    summary: str


def attribute_current_paper_strategy(session: Session) -> StrategyAttributionPayload:
    workspace = get_or_create_default_workspace(session)
    team_id = workspace.team.id
    events = list(
        session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id).order_by(CoreEventLog.sequence)).all()
    )
    orders = list(session.exec(select(PaperOrder).where(PaperOrder.team_id == team_id)).all())
    positions = list(session.exec(select(PaperPosition).where(PaperPosition.team_id == team_id)).all())
    reviews = list(
        session.exec(select(PaperReview).where(PaperReview.team_id == team_id).order_by(PaperReview.created_at)).all()
    )
    warnings: list[str] = []
    signal_quality = _signal_quality(events, orders, positions, warnings)
    expectancy = _expectancy_decomposition(orders, positions)
    max_drawdown = _max_drawdown(reviews)
    regime = _market_regime(reviews, max_drawdown)
    drawdown = _drawdown_source(reviews, max_drawdown, expectancy)

    if signal_quality.market_event_count == 0:
        warnings.append("missing_market_events")
    if signal_quality.trade_intent_count == 0:
        warnings.append("missing_trade_intents")
    if len(reviews) < 3:
        warnings.append("insufficient_review_history")
    if not [order for order in orders if order.status == PaperOrderStatus.filled]:
        warnings.append("no_filled_orders")
    warnings.append("market_regime_is_proxy")

    return StrategyAttributionPayload(
        strategy_id=DEFAULT_STRATEGY_ID,
        strategy_name=DEFAULT_STRATEGY_NAME,
        signal_quality=signal_quality,
        expectancy_decomposition=expectancy,
        regime=regime,
        drawdown=drawdown,
        data_quality_warnings=_dedupe(warnings),
        summary=_summary(signal_quality, expectancy, regime, drawdown),
    )


def _signal_quality(
    events: list[CoreEventLog],
    orders: list[PaperOrder],
    positions: list[PaperPosition],
    warnings: list[str],
) -> SignalQualityAttribution:
    market_events = [event for event in events if event.topic == "market_event"]
    trade_intents = [event for event in events if event.topic == "trade_intent"]
    confidences: list[float] = []
    for event in market_events:
        payload = _event_payload(event, warnings)
        confidence = payload.get("confidence") if payload is not None else None
        if isinstance(confidence, int | float):
            confidences.append(float(confidence))
    filled_orders = [order for order in orders if order.status == PaperOrderStatus.filled]
    return SignalQualityAttribution(
        market_event_count=len(market_events),
        trade_intent_count=len(trade_intents),
        actionable_signal_rate=_ratio(len(trade_intents), len(market_events)),
        average_confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        false_positive_rate=_false_positive_rate(filled_orders, positions),
    )


def _expectancy_decomposition(
    orders: list[PaperOrder],
    positions: list[PaperPosition],
) -> ExpectancyDecomposition:
    realized = round(sum(order.realized_pnl for order in orders if order.status == PaperOrderStatus.filled), 2)
    unrealized = round(sum(position.unrealized_pnl for position in positions), 2)
    return ExpectancyDecomposition(
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        closed_trade_component=realized,
        open_trade_component=unrealized,
        total_observed_pnl=round(realized + unrealized, 2),
    )


def _market_regime(reviews: list[PaperReview], max_drawdown: float) -> MarketRegimeAttribution:
    if len(reviews) < 3:
        return MarketRegimeAttribution(
            regime="insufficient_data",
            basis="少于 3 条复盘记录，不能判断市场环境代理状态。",
            review_count=len(reviews),
            equity_change=0.0,
        )
    first_equity = reviews[0].equity
    latest_equity = reviews[-1].equity
    equity_change = _ratio(latest_equity - first_equity, first_equity)
    if max_drawdown > 0.10:
        regime = "drawdown_pressure"
        basis = "复盘权益曲线从峰值回撤超过 10%。"
    elif equity_change >= 0.02:
        regime = "uptrend_capture"
        basis = "最新权益较首条复盘高出至少 2%。"
    else:
        regime = "range_bound"
        basis = "权益变化和回撤均未触发趋势或压力阈值。"
    return MarketRegimeAttribution(
        regime=regime,
        basis=basis,
        review_count=len(reviews),
        equity_change=equity_change,
    )


def _drawdown_source(
    reviews: list[PaperReview],
    max_drawdown: float,
    expectancy: ExpectancyDecomposition,
) -> DrawdownAttribution:
    if len(reviews) < 3:
        return DrawdownAttribution(
            source="insufficient_data",
            max_drawdown=max_drawdown,
            basis="少于 3 条复盘记录，回撤来源仅保留为数据不足。",
        )
    if expectancy.unrealized_pnl < 0:
        return DrawdownAttribution(
            source="open_position_pressure",
            max_drawdown=max_drawdown,
            basis="未平仓持仓存在浮亏，当前回撤主要归因于开放头寸压力。",
        )
    if expectancy.realized_pnl < 0:
        return DrawdownAttribution(
            source="closed_trade_losses",
            max_drawdown=max_drawdown,
            basis="已实现盈亏为负，当前回撤主要归因于已平仓交易亏损。",
        )
    return DrawdownAttribution(
        source="equity_curve_pressure",
        max_drawdown=max_drawdown,
        basis="未发现负的开放或已平仓组件，回撤暂归因于权益曲线波动。",
    )


def _false_positive_rate(orders: list[PaperOrder], positions: list[PaperPosition]) -> float:
    if not orders:
        return 0.0
    positions_by_ticker = {position.ticker: position for position in positions}
    false_positive_count = 0
    for order in orders:
        if order.side == PaperOrderSide.sell:
            if order.realized_pnl < 0:
                false_positive_count += 1
            continue
        position = positions_by_ticker.get(order.ticker)
        if position is not None and position.unrealized_pnl < 0:
            false_positive_count += 1
    return _ratio(false_positive_count, len(orders))


def _max_drawdown(reviews: list[PaperReview]) -> float:
    peak = 0.0
    worst = 0.0
    for review in reviews:
        peak = max(peak, review.equity)
        if peak <= 0:
            continue
        worst = max(worst, (peak - review.equity) / peak)
    return round(worst, 4)


def _event_payload(event: CoreEventLog, warnings: list[str]) -> dict | None:
    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError:
        warnings.append("malformed_event_payload")
        return None
    if not isinstance(payload, dict):
        warnings.append("malformed_event_payload")
        return None
    return payload


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _summary(
    signal_quality: SignalQualityAttribution,
    expectancy: ExpectancyDecomposition,
    regime: MarketRegimeAttribution,
    drawdown: DrawdownAttribution,
) -> str:
    return (
        f"可行动信号率 {signal_quality.actionable_signal_rate:.2%}，"
        f"误报率 {signal_quality.false_positive_rate:.2%}，"
        f"观测盈亏 {expectancy.total_observed_pnl:.2f}，"
        f"环境代理 {regime.regime}，回撤来源 {drawdown.source}。"
    )
