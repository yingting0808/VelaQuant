import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.data.providers.base import MarketDataProvider, PriceHistoryBar
from app.domain.models import CoreEventLog, PaperOrder, PaperOrderSide, PaperOrderStatus, PaperPosition, PaperReview, PaperRun
from app.services.market_calendar import current_market_trading_day
from app.services.strategy_event_filters import filter_strategy_trade_events
from app.services.strategy_evaluation import DEFAULT_STRATEGY_ID, DEFAULT_STRATEGY_NAME
from app.services.workspace import get_or_create_default_workspace


class SignalQualityAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_event_count: int
    trade_intent_count: int
    actionable_signal_rate: float
    average_confidence: float
    false_positive_rate: float


class TickerSignalAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    market_event_count: int
    trade_intent_count: int
    candidate_score_count: int
    average_candidate_score: float
    latest_candidate_score: float | None = None
    filled_order_count: int
    false_positive_count: int
    false_positive_rate: float
    average_confidence: float
    realized_pnl: float
    unrealized_pnl: float
    observed_pnl: float


class SignalDecayAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_days: int
    open_position_count: int
    stale_open_position_count: int
    stale_tickers: list[str]
    average_holding_days: float
    basis: str


class AttributionComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["trend_component", "volatility_component", "timing_component", "risk_component", "noise_component"]
    value: float
    basis: str


class ExpectancyDecomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    realized_pnl: float
    unrealized_pnl: float
    closed_trade_component: float
    open_trade_component: float
    total_observed_pnl: float
    components: list[AttributionComponent] = Field(default_factory=list)


class MarketRegimeAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regime: Literal["insufficient_data", "drawdown_pressure", "uptrend_capture", "range_bound"]
    basis: str
    review_count: int
    equity_change: float


class RegimePerformanceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regime: Literal["trend_market", "range_market", "high_volatility", "insufficient_data"]
    ticker_count: int
    observed_pnl: float
    average_return: float
    average_volatility: float
    sample_count: int
    sharpe_proxy: float
    tickers: list[str]
    basis: str


class RegimeBreakdownPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_regime: Literal["trend_market", "range_market", "high_volatility", "insufficient_data"]
    items: list[RegimePerformanceItem]
    basis: str


class DrawdownAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["insufficient_data", "open_position_pressure", "closed_trade_losses", "equity_curve_pressure"]
    max_drawdown: float
    basis: str
    contributors: list["DrawdownContributor"] = Field(default_factory=list)


class DrawdownContributor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["market_driven", "signal_failure", "execution_lag", "risk_overreach"]
    value: float
    basis: str


class StrategyAttributionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    strategy_name: str
    signal_quality: SignalQualityAttribution
    ticker_diagnostics: list[TickerSignalAttribution]
    signal_decay: SignalDecayAttribution
    expectancy_decomposition: ExpectancyDecomposition
    regime: MarketRegimeAttribution
    regime_breakdown: RegimeBreakdownPayload
    drawdown: DrawdownAttribution
    data_quality_warnings: list[str]
    summary: str


def attribute_current_paper_strategy(
    session: Session,
    provider: MarketDataProvider | None = None,
    *,
    as_of_trading_day: str | None = None,
) -> StrategyAttributionPayload:
    workspace = get_or_create_default_workspace(session)
    team_id = workspace.team.id
    as_of_trading_day = as_of_trading_day or _current_trading_day()
    events = _events_as_of(session, team_id, as_of_trading_day)
    orders = [
        order
        for order in session.exec(select(PaperOrder).where(PaperOrder.team_id == team_id)).all()
        if order.strategy_id == DEFAULT_STRATEGY_ID
        and order.submitted_at.date().isoformat() <= as_of_trading_day
    ]
    positions = list(session.exec(select(PaperPosition).where(PaperPosition.team_id == team_id)).all())
    reviews = list(
        session.exec(
            select(PaperReview)
            .where(PaperReview.team_id == team_id)
            .where(PaperReview.trading_day <= as_of_trading_day)
            .order_by(PaperReview.created_at)
        ).all()
    )
    warnings: list[str] = []
    if positions and _has_future_runs(session, team_id, as_of_trading_day):
        warnings.append("position_snapshot_may_include_future_run_state")
    signal_quality = _signal_quality(events, orders, positions, warnings)
    expectancy = _expectancy_decomposition(orders, positions)
    max_drawdown = _max_drawdown(reviews)
    regime = _market_regime(reviews, max_drawdown)
    drawdown = _drawdown_source(reviews, max_drawdown, expectancy)
    ticker_diagnostics = _ticker_diagnostics(events, orders, positions, warnings)
    regime_breakdown = _regime_breakdown(ticker_diagnostics, provider, warnings)
    signal_decay = _signal_decay(events, orders, positions, reviews)
    expectancy.components = _expectancy_components(expectancy, signal_quality, orders, regime, regime_breakdown)
    drawdown.contributors = _drawdown_contributors(drawdown, expectancy, orders)

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
        ticker_diagnostics=ticker_diagnostics,
        signal_decay=signal_decay,
        expectancy_decomposition=expectancy,
        regime=regime,
        regime_breakdown=regime_breakdown,
        drawdown=drawdown,
        data_quality_warnings=_dedupe(warnings),
        summary=_summary(signal_quality, expectancy, regime, drawdown),
    )


def _events_as_of(session: Session, team_id, as_of_trading_day: str) -> list[CoreEventLog]:
    eligible_run_ids = {
        run.id
        for run in session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.trading_day <= as_of_trading_day)
        ).all()
    }
    events = session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id).order_by(CoreEventLog.sequence)).all()
    eligible_events = [
        event
        for event in events
        if (event.run_id in eligible_run_ids)
        or (event.run_id is None and event.published_at.date().isoformat() <= as_of_trading_day)
    ]
    return filter_strategy_trade_events(eligible_events)


def _has_future_runs(session: Session, team_id, as_of_trading_day: str) -> bool:
    return (
        session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.trading_day > as_of_trading_day)
        ).first()
        is not None
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


def _ticker_diagnostics(
    events: list[CoreEventLog],
    orders: list[PaperOrder],
    positions: list[PaperPosition],
    warnings: list[str],
) -> list[TickerSignalAttribution]:
    rows: dict[str, dict[str, float | int | list[float]]] = {}
    for event in events:
        if event.topic not in {"market_event", "trade_intent", "trade_explanation"}:
            continue
        payload = _event_payload(event, warnings)
        ticker = _payload_ticker(payload)
        if ticker is None:
            continue
        row = _ticker_row(rows, ticker)
        if event.topic == "market_event":
            row["market_event_count"] = int(row["market_event_count"]) + 1
            confidence = payload.get("confidence") if payload is not None else None
            if isinstance(confidence, int | float):
                confidences = row["confidences"]
                if isinstance(confidences, list):
                    confidences.append(float(confidence))
        elif event.topic == "trade_intent":
            row["trade_intent_count"] = int(row["trade_intent_count"]) + 1
        elif event.topic == "trade_explanation":
            score = _candidate_score(payload)
            if score is not None:
                candidate_scores = row["candidate_scores"]
                if isinstance(candidate_scores, list):
                    candidate_scores.append(score)

    positions_by_ticker = {position.ticker: position for position in positions}
    for order in orders:
        row = _ticker_row(rows, order.ticker)
        if order.status == PaperOrderStatus.filled:
            row["filled_order_count"] = int(row["filled_order_count"]) + 1
            row["realized_pnl"] = float(row["realized_pnl"]) + order.realized_pnl
            if _order_is_false_positive(order, positions_by_ticker):
                row["false_positive_count"] = int(row["false_positive_count"]) + 1

    for position in positions:
        row = _ticker_row(rows, position.ticker)
        row["unrealized_pnl"] = float(row["unrealized_pnl"]) + position.unrealized_pnl

    diagnostics: list[TickerSignalAttribution] = []
    for ticker in sorted(rows):
        row = rows[ticker]
        confidences = row["confidences"] if isinstance(row["confidences"], list) else []
        candidate_scores = row["candidate_scores"] if isinstance(row["candidate_scores"], list) else []
        filled_order_count = int(row["filled_order_count"])
        false_positive_count = int(row["false_positive_count"])
        realized = round(float(row["realized_pnl"]), 2)
        unrealized = round(float(row["unrealized_pnl"]), 2)
        diagnostics.append(
            TickerSignalAttribution(
                ticker=ticker,
                market_event_count=int(row["market_event_count"]),
                trade_intent_count=int(row["trade_intent_count"]),
                candidate_score_count=len(candidate_scores),
                average_candidate_score=round(sum(candidate_scores) / len(candidate_scores), 2)
                if candidate_scores
                else 0.0,
                latest_candidate_score=round(candidate_scores[-1], 2) if candidate_scores else None,
                filled_order_count=filled_order_count,
                false_positive_count=false_positive_count,
                false_positive_rate=_ratio(false_positive_count, filled_order_count),
                average_confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                observed_pnl=round(realized + unrealized, 2),
            )
        )
    return diagnostics


def _ticker_row(rows: dict[str, dict[str, float | int | list[float]]], ticker: str) -> dict[str, float | int | list[float]]:
    if ticker not in rows:
        rows[ticker] = {
            "market_event_count": 0,
            "trade_intent_count": 0,
            "filled_order_count": 0,
            "false_positive_count": 0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "confidences": [],
            "candidate_scores": [],
        }
    return rows[ticker]


def _payload_ticker(payload: dict | None) -> str | None:
    if payload is None:
        return None
    ticker = payload.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()
    market_event = payload.get("market_event")
    if isinstance(market_event, dict):
        nested_ticker = market_event.get("ticker")
        if isinstance(nested_ticker, str) and nested_ticker.strip():
            return nested_ticker.strip().upper()
    return None


def _candidate_score(payload: dict | None) -> float | None:
    if payload is None:
        return None
    direct_score = payload.get("final_score")
    if isinstance(direct_score, int | float):
        return float(direct_score)
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        return None
    for item in reversed(evidence):
        if not isinstance(item, str):
            continue
        key, separator, raw_value = item.partition("=")
        if separator != "=" or key.strip() != "final_score":
            continue
        try:
            return float(raw_value.strip())
        except ValueError:
            return None
    return None


def _signal_decay(
    events: list[CoreEventLog],
    orders: list[PaperOrder],
    positions: list[PaperPosition],
    reviews: list[PaperReview],
    threshold_days: int = 5,
) -> SignalDecayAttribution:
    open_positions = [position for position in positions if position.quantity > 0]
    as_of = _attribution_as_of(events, orders, positions, reviews)
    buy_orders_by_ticker: dict[str, list[PaperOrder]] = {}
    for order in orders:
        if order.status == PaperOrderStatus.filled and order.side == PaperOrderSide.buy:
            buy_orders_by_ticker.setdefault(order.ticker, []).append(order)

    holding_days: list[float] = []
    stale_tickers: list[str] = []
    for position in open_positions:
        buy_orders = sorted(buy_orders_by_ticker.get(position.ticker, []), key=lambda order: order.submitted_at)
        if not buy_orders:
            continue
        latest_buy = buy_orders[-1]
        age_days = max((as_of - _aware_datetime(latest_buy.submitted_at)).total_seconds() / 86400, 0.0)
        rounded_age = round(age_days, 2)
        holding_days.append(rounded_age)
        if age_days >= threshold_days:
            stale_tickers.append(position.ticker)

    return SignalDecayAttribution(
        threshold_days=threshold_days,
        open_position_count=len(open_positions),
        stale_open_position_count=len(stale_tickers),
        stale_tickers=sorted(stale_tickers),
        average_holding_days=round(sum(holding_days) / len(holding_days), 2) if holding_days else 0.0,
        basis=f"以最新账本时间为 as_of，开放持仓超过 {threshold_days} 天视为信号衰减观察对象。",
    )


def _attribution_as_of(
    events: list[CoreEventLog],
    orders: list[PaperOrder],
    positions: list[PaperPosition],
    reviews: list[PaperReview],
) -> datetime:
    timestamps: list[datetime] = []
    timestamps.extend(event.published_at for event in events)
    timestamps.extend(order.submitted_at for order in orders)
    timestamps.extend(position.updated_at for position in positions)
    timestamps.extend(review.created_at for review in reviews)
    if not timestamps:
        return datetime.now(timezone.utc)
    return max(_aware_datetime(item) for item in timestamps)


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _current_trading_day() -> str:
    return current_market_trading_day()


def _expectancy_components(
    expectancy: ExpectancyDecomposition,
    signal_quality: SignalQualityAttribution,
    orders: list[PaperOrder],
    regime: MarketRegimeAttribution,
    regime_breakdown: RegimeBreakdownPayload,
) -> list[AttributionComponent]:
    rejected_order_count = len([order for order in orders if order.status == PaperOrderStatus.rejected])
    noise_value = round(min(expectancy.realized_pnl, 0.0) + min(expectancy.unrealized_pnl, 0.0), 2)
    trend_value = expectancy.total_observed_pnl if regime.regime == "uptrend_capture" else 0.0
    high_volatility_pnl = round(
        sum(item.observed_pnl for item in regime_breakdown.items if item.regime == "high_volatility"),
        2,
    )
    return [
        AttributionComponent(
            name="trend_component",
            value=round(trend_value, 2),
            basis="环境代理为 uptrend_capture 时，把观测盈亏标记为趋势捕获组件。",
        ),
        AttributionComponent(
            name="volatility_component",
            value=high_volatility_pnl,
            basis="高波动市场桶内的观测盈亏，作为波动环境贡献代理。",
        ),
        AttributionComponent(
            name="timing_component",
            value=round(expectancy.unrealized_pnl, 2),
            basis="开放持仓浮盈/浮亏作为入场时点与持仓管理代理。",
        ),
        AttributionComponent(
            name="risk_component",
            value=round(-float(rejected_order_count), 2),
            basis="被风控拒绝的订单数量作为风险摩擦代理。",
        ),
        AttributionComponent(
            name="noise_component",
            value=noise_value,
            basis="负的已实现/未实现盈亏叠加误报率，作为信号噪声代理。",
        ),
    ]


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


def _regime_breakdown(
    ticker_diagnostics: list[TickerSignalAttribution],
    provider: MarketDataProvider | None,
    warnings: list[str],
) -> RegimeBreakdownPayload:
    rows = {
        "trend_market": _regime_row("trend_market", "价格首尾变化绝对值达到 2%。"),
        "range_market": _regime_row("range_market", "价格首尾变化和波动率均未触发趋势或高波动阈值。"),
        "high_volatility": _regime_row("high_volatility", "日收益波动率达到 4%。"),
        "insufficient_data": _regime_row("insufficient_data", "少于 3 个有效收盘价或行情源不可用。"),
    }
    if provider is None:
        warnings.append("missing_market_history_provider")
        for diagnostic in ticker_diagnostics:
            _add_regime_row(rows["insufficient_data"], diagnostic, 0.0, 0.0, 0, 0.0)
        return _regime_payload(rows)

    for diagnostic in ticker_diagnostics:
        try:
            history = provider.get_price_history(diagnostic.ticker)
        except Exception:
            warnings.append("market_history_unavailable")
            _add_regime_row(rows["insufficient_data"], diagnostic, 0.0, 0.0, 0, 0.0)
            continue
        label, total_return, volatility, sample_count, sharpe_proxy = _classify_price_history(history)
        _add_regime_row(rows[label], diagnostic, total_return, volatility, sample_count, sharpe_proxy)
    return _regime_payload(rows)


def _regime_row(regime: str, basis: str) -> dict:
    return {
        "regime": regime,
        "ticker_count": 0,
        "observed_pnl": 0.0,
        "returns": [],
        "volatilities": [],
        "sample_count": 0,
        "sharpe_values": [],
        "tickers": [],
        "basis": basis,
    }


def _add_regime_row(
    row: dict,
    diagnostic: TickerSignalAttribution,
    total_return: float,
    volatility: float,
    sample_count: int,
    sharpe_proxy: float,
) -> None:
    row["ticker_count"] += 1
    row["observed_pnl"] = round(row["observed_pnl"] + diagnostic.observed_pnl, 2)
    row["returns"].append(total_return)
    row["volatilities"].append(volatility)
    row["sample_count"] += sample_count
    row["sharpe_values"].append(sharpe_proxy)
    row["tickers"].append(diagnostic.ticker)


def _regime_payload(rows: dict[str, dict]) -> RegimeBreakdownPayload:
    items: list[RegimePerformanceItem] = []
    for regime in ("trend_market", "range_market", "high_volatility", "insufficient_data"):
        row = rows[regime]
        returns = row["returns"]
        volatilities = row["volatilities"]
        sharpe_values = row["sharpe_values"]
        items.append(
            RegimePerformanceItem(
                regime=regime,
                ticker_count=row["ticker_count"],
                observed_pnl=row["observed_pnl"],
                average_return=round(sum(returns) / len(returns), 4) if returns else 0.0,
                average_volatility=round(sum(volatilities) / len(volatilities), 4) if volatilities else 0.0,
                sample_count=row["sample_count"],
                sharpe_proxy=round(sum(sharpe_values) / len(sharpe_values), 4) if sharpe_values else 0.0,
                tickers=sorted(row["tickers"]),
                basis=row["basis"],
            )
        )
    populated = [item for item in items if item.ticker_count > 0]
    primary = max(populated, key=lambda item: abs(item.observed_pnl)).regime if populated else "insufficient_data"
    return RegimeBreakdownPayload(
        primary_regime=primary,
        items=items,
        basis="基于各 ticker 最近价格历史的首尾收益和日收益波动率，对观测盈亏做市场环境代理拆分。",
    )


def _classify_price_history(
    history: list[PriceHistoryBar],
) -> tuple[Literal["trend_market", "range_market", "high_volatility", "insufficient_data"], float, float, int, float]:
    closes = [float(bar.close) for bar in history if bar.close is not None and bar.close > 0]
    if len(closes) < 3:
        return "insufficient_data", 0.0, 0.0, 0, 0.0
    total_return = (closes[-1] - closes[0]) / closes[0]
    returns = [(closes[index] - closes[index - 1]) / closes[index - 1] for index in range(1, len(closes))]
    volatility = _sample_volatility(returns)
    sharpe_proxy = _sharpe_proxy(returns)
    if volatility >= 0.04:
        return "high_volatility", round(total_return, 4), volatility, len(returns), sharpe_proxy
    if abs(total_return) >= 0.02:
        return "trend_market", round(total_return, 4), volatility, len(returns), sharpe_proxy
    return "range_market", round(total_return, 4), volatility, len(returns), sharpe_proxy


def _sample_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    average = sum(returns) / len(returns)
    variance = sum((item - average) ** 2 for item in returns) / len(returns)
    return round(variance ** 0.5, 4)


def _sharpe_proxy(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    average = sum(returns) / len(returns)
    variance = sum((item - average) ** 2 for item in returns) / len(returns)
    volatility = variance ** 0.5
    return round(average / max(volatility, 0.01), 4)


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


def _drawdown_contributors(
    drawdown: DrawdownAttribution,
    expectancy: ExpectancyDecomposition,
    orders: list[PaperOrder],
) -> list[DrawdownContributor]:
    rejected_order_count = len([order for order in orders if order.status == PaperOrderStatus.rejected])
    signal_failure = round(min(expectancy.realized_pnl, 0.0) + min(expectancy.unrealized_pnl, 0.0), 2)
    return [
        DrawdownContributor(
            name="market_driven",
            value=drawdown.max_drawdown,
            basis="当前只有权益曲线代理，市场驱动贡献先用最大回撤表达。",
        ),
        DrawdownContributor(
            name="signal_failure",
            value=signal_failure,
            basis="负的已实现和未实现盈亏合计，作为信号失效压力代理。",
        ),
        DrawdownContributor(
            name="execution_lag",
            value=0.0,
            basis="当前 mock/同步执行没有 broker 延迟数据，保留稳定字段。",
        ),
        DrawdownContributor(
            name="risk_overreach",
            value=float(rejected_order_count),
            basis="被 Risk Engine 拒绝的订单数量，作为风险越界代理。",
        ),
    ]


def _false_positive_rate(orders: list[PaperOrder], positions: list[PaperPosition]) -> float:
    if not orders:
        return 0.0
    positions_by_ticker = {position.ticker: position for position in positions}
    false_positive_count = 0
    for order in orders:
        if _order_is_false_positive(order, positions_by_ticker):
            false_positive_count += 1
    return _ratio(false_positive_count, len(orders))


def _order_is_false_positive(order: PaperOrder, positions_by_ticker: dict[str, PaperPosition]) -> bool:
    if order.side == PaperOrderSide.sell:
        return order.realized_pnl < 0
    position = positions_by_ticker.get(order.ticker)
    return position is not None and position.unrealized_pnl < 0


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
