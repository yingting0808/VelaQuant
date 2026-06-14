from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.trading_core.event_bus import EventEnvelope, InMemoryEventBus, TradingEventTopic
from app.trading_core.events import MarketEvent, StrategyInputEvent
from app.trading_core.execution import CoreOrder, ExecutionEngine, order_state_event
from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskEngine
from app.trading_core.strategy import TradeIntent
from app.trading_core.strategy_engine import StrategyEngine


class StrategyExecutionBindingLike(Protocol):
    strategy_id: str
    strategy_engine: StrategyEngine


class TradingEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: MarketEvent
    intents: list[TradeIntent]
    orders: list[CoreOrder]
    events: list[EventEnvelope] = Field(default_factory=list)


class TradingEngine:
    def __init__(
        self,
        strategy_binding: StrategyExecutionBindingLike,
        risk_engine: RiskEngine,
        event_bus: InMemoryEventBus,
    ) -> None:
        if not hasattr(strategy_binding, "strategy_engine") or not hasattr(strategy_binding, "strategy_id"):
            raise TypeError("TradingEngine requires a registry StrategyExecutionBinding.")
        self.strategy_binding = strategy_binding
        self.strategy_engine = strategy_binding.strategy_engine
        self.execution_engine = ExecutionEngine(risk_engine)
        self.event_bus = event_bus

    def process_event(self, event: MarketEvent, portfolio: PortfolioState) -> TradingEngineResult:
        event_start_index = len(self.event_bus.history)
        market_envelope = self.event_bus.publish(TradingEventTopic.market_event, event)
        strategy_input = StrategyInputEvent(market_event=event, portfolio=portfolio)
        strategy_input_envelope = self.event_bus.publish(
            TradingEventTopic.strategy_input,
            strategy_input,
            causation_id=market_envelope.event_id,
            correlation_id=market_envelope.correlation_id,
        )
        strategy_result = self.strategy_engine.generate_intents(event, portfolio)
        intents = strategy_result.intents
        orders: list[CoreOrder] = []
        for intent in intents:
            trade_intent_envelope = self.event_bus.publish(
                TradingEventTopic.trade_intent,
                intent,
                causation_id=strategy_input_envelope.event_id,
                correlation_id=strategy_input_envelope.correlation_id,
            )
            order = self.execution_engine.submit_intent(intent, portfolio)
            orders.append(order)
            risk_decision_envelope = None
            if order.risk_decision is not None:
                risk_decision_envelope = self.event_bus.publish(
                    TradingEventTopic.risk_decision,
                    order.risk_decision,
                    causation_id=trade_intent_envelope.event_id,
                    correlation_id=trade_intent_envelope.correlation_id,
                )
            self.event_bus.publish(
                TradingEventTopic.order_state,
                order_state_event(order),
                causation_id=(
                    risk_decision_envelope.event_id
                    if risk_decision_envelope is not None
                    else trade_intent_envelope.event_id
                ),
                correlation_id=trade_intent_envelope.correlation_id,
            )
        events = self.event_bus.history[event_start_index:]
        return TradingEngineResult(event=event, intents=intents, orders=orders, events=events)
