from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

import app.trading_core as trading_core
from app.services.strategy_registry import StrategyExecutionBinding, StrategyExecutionMode
from app.trading_core.engine import TradingEngine
from app.trading_core.event_bus import InMemoryEventBus, RedisStreamEventBus, TradingEventTopic
from app.trading_core.events import EventSource, MarketEvent, MarketEventType, Sentiment, StrategyInputEvent
from app.trading_core.execution import ExecutionEngine, ExecutionReport, ExecutionReportStatus, OrderState
from app.trading_core.portfolio import PortfolioPosition, PortfolioState
from app.trading_core.risk import RiskDecisionStatus, RiskEngine, RiskLimits
from app.trading_core.strategy_engine import StrategyEngine
from app.trading_core.strategy import DeterministicWatchlistStrategy, TradeIntent, TradeIntentSide


def _strategy_binding(notional: float = 1500) -> StrategyExecutionBinding:
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=notional)
    return StrategyExecutionBinding(
        strategy_id="deterministic_watchlist_v1",
        name="Deterministic Watchlist Strategy",
        version="v1",
        execution_mode=StrategyExecutionMode.paper,
        strategy_engine=StrategyEngine(strategy_id="deterministic_watchlist_v1", strategy=strategy),
        supports_live=False,
        supports_hot_swap=True,
    )


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


def test_trading_core_package_exports_event_and_execution_boundaries():
    assert trading_core.InMemoryEventBus is InMemoryEventBus
    assert trading_core.TradingEventTopic is TradingEventTopic
    assert trading_core.ExecutionReport is ExecutionReport
    assert trading_core.ExecutionReportStatus is ExecutionReportStatus


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


class FakeRedisStreamClient:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, str]]] = []

    def xadd(self, stream_name: str, fields: dict[str, str]):
        self.entries.append((stream_name, fields))
        return "1-0"


def test_redis_stream_event_bus_writes_event_envelopes_to_stream():
    client = FakeRedisStreamClient()
    bus = RedisStreamEventBus(client=client, stream_name="trading:events")

    envelope = bus.publish(TradingEventTopic.market_event, _event())

    assert envelope.topic == TradingEventTopic.market_event
    assert len(bus.history) == 1
    assert client.entries[0][0] == "trading:events"
    fields = client.entries[0][1]
    assert fields["event_id"] == str(envelope.event_id)
    assert fields["event_type"] == "market_event"
    assert fields["topic"] == "market_event"
    assert fields["correlation_id"] == str(envelope.correlation_id)
    assert fields["payload_json"]


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


def test_strategy_engine_generates_intents_for_registered_strategy_id():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    engine = StrategyEngine(strategy_id="deterministic_watchlist_v1", strategy=strategy)
    portfolio = PortfolioState(cash=100000, equity=100000)

    result = engine.generate_intents(_event(), portfolio)

    assert result.strategy_id == "deterministic_watchlist_v1"
    assert len(result.intents) == 1
    assert result.intents[0].ticker == "NVDA"


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


def test_risk_engine_blocks_new_buys_but_allows_risk_reducing_sell_when_daily_order_limit_is_full():
    risk = RiskEngine(RiskLimits(max_order_notional=5000, max_daily_orders=5))
    portfolio = PortfolioState(
        cash=100000,
        equity=100000,
        positions=[PortfolioPosition(ticker="NVDA", quantity=10, market_value=2500)],
        orders_today=5,
    )
    buy_intent = TradeIntent(ticker="AAPL", side=TradeIntentSide.buy, notional=1500, reason="test buy")
    sell_intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.sell, notional=1500, reason="risk reducing exit")

    buy_decision = risk.evaluate(buy_intent, portfolio)
    sell_decision = risk.evaluate(sell_intent, portfolio)

    assert buy_decision.status == RiskDecisionStatus.rejected
    assert buy_decision.code == "max_daily_orders"
    assert sell_decision.status == RiskDecisionStatus.approved
    assert sell_decision.code == "approved"


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


class RecordingExecutionAdapter:
    def __init__(self, report: ExecutionReport | None = None) -> None:
        self.submitted_order_ids: list[str] = []
        self.report = report or ExecutionReport(
            status=ExecutionReportStatus.filled,
            broker_order_id="recording-1",
            average_fill_price=123.45,
            message="recording adapter fill",
        )

    def submit_order(self, order, portfolio):
        self.submitted_order_ids.append(str(order.order_id))
        return self.report


def test_execution_engine_does_not_call_adapter_when_risk_rejects_intent():
    adapter = RecordingExecutionAdapter()
    risk = RiskEngine(RiskLimits(max_order_notional=1000))
    execution = ExecutionEngine(risk, adapter=adapter)
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=5000, reason="test")

    order = execution.submit_intent(intent, portfolio)

    assert order.current_state == OrderState.rejected
    assert adapter.submitted_order_ids == []


def test_execution_engine_uses_adapter_report_for_filled_order():
    adapter = RecordingExecutionAdapter()
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    execution = ExecutionEngine(risk, adapter=adapter)
    portfolio = PortfolioState(cash=100000, equity=100000)
    intent = TradeIntent(ticker="NVDA", side=TradeIntentSide.buy, notional=1500, reason="test")

    order = execution.submit_intent(intent, portfolio)

    assert adapter.submitted_order_ids == [str(order.order_id)]
    assert order.current_state == OrderState.filled
    assert order.broker_order_id == "recording-1"
    assert order.average_fill_price == 123.45
    assert order.state_history[-1].reason == "recording adapter fill"


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
    bus = InMemoryEventBus()
    binding = _strategy_binding()
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    engine = TradingEngine(strategy_binding=binding, risk_engine=risk, event_bus=bus)
    portfolio = PortfolioState(cash=100000, equity=100000)

    result = engine.process_event(_event(), portfolio)

    assert engine.strategy_binding is binding
    assert len(result.intents) == 1
    assert len(result.orders) == 1
    assert result.orders[0].current_state == OrderState.filled


def test_trading_engine_requires_event_bus():
    binding = _strategy_binding()
    risk = RiskEngine(RiskLimits(max_order_notional=5000))

    with pytest.raises(TypeError):
        TradingEngine(strategy_binding=binding, risk_engine=risk)


def test_trading_engine_rejects_bare_strategy_engine():
    strategy = DeterministicWatchlistStrategy(watchlist=["NVDA"], notional=1500)
    strategy_engine = StrategyEngine(strategy_id="deterministic_watchlist_v1", strategy=strategy)
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    bus = InMemoryEventBus()

    with pytest.raises(TypeError, match="registry StrategyExecutionBinding"):
        TradingEngine(strategy_binding=strategy_engine, risk_engine=risk, event_bus=bus)


def test_trading_engine_publishes_replayable_core_event_chain():
    bus = InMemoryEventBus()
    binding = _strategy_binding()
    risk = RiskEngine(RiskLimits(max_order_notional=5000))
    engine = TradingEngine(strategy_binding=binding, risk_engine=risk, event_bus=bus)
    portfolio = PortfolioState(cash=100000, equity=100000)

    result = engine.process_event(_event(), portfolio)

    assert [event.topic for event in bus.history] == [
        TradingEventTopic.market_event,
        TradingEventTopic.strategy_input,
        TradingEventTopic.trade_intent,
        TradingEventTopic.risk_decision,
        TradingEventTopic.order_state,
    ]
    assert bus.history[1].payload.market_event.event_id == result.event.event_id
    assert bus.history[2].payload.intent_id == result.intents[0].intent_id
    assert bus.history[3].payload.status == RiskDecisionStatus.approved
    assert bus.history[4].payload.order_id == result.orders[0].order_id
    assert bus.history[4].payload.current_state == OrderState.filled
    assert len({event.correlation_id for event in bus.history}) == 1
