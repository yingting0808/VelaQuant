from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.trading_core.engine import TradingEngine
from app.trading_core.event_bus import InMemoryEventBus, TradingEventTopic
from app.trading_core.events import EventSource, MarketEvent, MarketEventType, Sentiment, StrategyInputEvent
from app.trading_core.execution import ExecutionEngine, OrderState
from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskDecisionStatus, RiskEngine, RiskLimits
from app.trading_core.strategy import DeterministicWatchlistStrategy, TradeIntent, TradeIntentSide


def _event() -> MarketEvent:
    return MarketEvent(
        source=EventSource.ai_structured,
        event_type=MarketEventType.earnings,
        ticker="NVDA",
        occurred_at=datetime(2026, 6, 13, tzinfo=timezone.utc),
        summary="NVDA reported stronger than expected data center revenue.",
        sentiment=Sentiment.positive,
        confidence=0.86,
        impact_score=0.74,
    )


def test_market_event_schema_does_not_include_trade_action_fields():
    event = _event()

    payload = event.model_dump()

    assert "side" not in payload
    assert "action" not in payload
    assert "quantity" not in payload
    assert "order_type" not in payload


def test_market_event_rejects_trade_action_fields_from_ai_payload():
    with pytest.raises(ValidationError):
        MarketEvent(
            source=EventSource.ai_structured,
            event_type=MarketEventType.earnings,
            ticker="NVDA",
            occurred_at=datetime(2026, 6, 13, tzinfo=timezone.utc),
            summary="NVDA beat expectations.",
            sentiment=Sentiment.positive,
            confidence=0.86,
            impact_score=0.74,
            action="buy",
        )


def test_strategy_input_event_wraps_market_event_and_portfolio_snapshot():
    portfolio = PortfolioState(cash=100000, equity=100000)
    strategy_input = StrategyInputEvent(market_event=_event(), portfolio=portfolio)

    assert strategy_input.market_event.ticker == "NVDA"
    assert strategy_input.portfolio == portfolio


def test_event_bus_records_and_dispatches_events_in_publish_order():
    bus = InMemoryEventBus()
    handled_topics: list[TradingEventTopic] = []
    bus.subscribe(TradingEventTopic.market_event, lambda event: handled_topics.append(event.topic))
    bus.subscribe(TradingEventTopic.trade_intent, lambda event: handled_topics.append(event.topic))

    first = bus.publish(TradingEventTopic.market_event, _event())
    second = bus.publish(
        TradingEventTopic.trade_intent,
        TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=1500, reason="test"),
        causation_id=first.event_id,
        correlation_id=first.correlation_id,
    )

    assert [event.topic for event in bus.history] == [TradingEventTopic.market_event, TradingEventTopic.trade_intent]
    assert handled_topics == [TradingEventTopic.market_event, TradingEventTopic.trade_intent]
    assert second.sequence == first.sequence + 1
    assert second.causation_id == first.event_id
    assert second.correlation_id == first.correlation_id


def test_strategy_converts_structured_event_to_trade_intent_deterministically():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    portfolio = PortfolioState(cash=100000, equity=100000)
    event = _event()

    first = strategy.generate_intents(event, portfolio)
    second = strategy.generate_intents(event, portfolio)

    assert first == second
    assert len(first) == 1
    assert first[0].ticker == "NVDA"
    assert first[0].side == TradeIntentSide.buy
    assert first[0].notional == 1500


def test_strategy_ignores_low_confidence_event():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    portfolio = PortfolioState(cash=100000, equity=100000)
    event = _event().model_copy(update={"confidence": 0.4})

    assert strategy.generate_intents(event, portfolio) == []


def test_risk_engine_rejects_oversized_trade_intent():
    risk = RiskEngine(RiskLimits(max_order_notional=1000))
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=5000, reason="test")

    decision = risk.evaluate(intent, portfolio)

    assert decision.status == RiskDecisionStatus.rejected
    assert decision.code == "max_order_notional"
    assert "exceeds" in decision.reason


def test_execution_engine_does_not_fill_rejected_intent():
    risk = RiskEngine(RiskLimits(max_order_notional=1000))
    execution = ExecutionEngine(risk)
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=5000, reason="test")

    order = execution.submit_intent(intent, portfolio)

    assert order.current_state == OrderState.rejected
    assert [state.state for state in order.state_history] == [OrderState.new, OrderState.validated, OrderState.rejected]
    assert order.risk_decision is not None
    assert order.risk_decision.status == RiskDecisionStatus.rejected


def test_execution_engine_records_approved_order_state_history():
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    execution = ExecutionEngine(risk)
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=1500, reason="test")

    order = execution.submit_intent(intent, portfolio)

    assert [state.state for state in order.state_history] == [
        OrderState.new,
        OrderState.validated,
        OrderState.risk_approved,
        OrderState.sent,
        OrderState.filled,
    ]


def test_trading_engine_processes_event_through_strategy_risk_and_execution():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    engine = TradingEngine(strategy=strategy, risk_engine=risk)
    portfolio = PortfolioState(cash=100000, equity=100000)

    result = engine.process_event(_event(), portfolio)

    assert len(result.intents) == 1
    assert len(result.orders) == 1
    assert result.orders[0].current_state == OrderState.filled
