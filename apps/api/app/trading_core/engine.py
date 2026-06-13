from pydantic import BaseModel, ConfigDict

from app.trading_core.event_bus import InMemoryEventBus, TradingEventTopic
from app.trading_core.events import MarketEvent, StrategyInputEvent
from app.trading_core.execution import CoreOrder, ExecutionEngine, order_state_event
from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskEngine
from app.trading_core.strategy import Strategy, TradeIntent


class TradingEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: MarketEvent
    intents: list[TradeIntent]
    orders: list[CoreOrder]


class TradingEngine:
    def __init__(
        self,
        strategy: Strategy,
        risk_engine: RiskEngine,
        event_bus: InMemoryEventBus | None = None,
    ) -> None:
        self.strategy = strategy
        self.execution_engine = ExecutionEngine(risk_engine)
        self.event_bus = event_bus

    def process_event(self, event: MarketEvent, portfolio: PortfolioState) -> TradingEngineResult:
        market_envelope = None
        strategy_input_envelope = None
        if self.event_bus is not None:
            market_envelope = self.event_bus.publish(TradingEventTopic.market_event, event)
            strategy_input = StrategyInputEvent(market_event=event, portfolio=portfolio)
            strategy_input_envelope = self.event_bus.publish(
                TradingEventTopic.strategy_input,
                strategy_input,
                causation_id=market_envelope.event_id,
                correlation_id=market_envelope.correlation_id,
            )
        intents = self.strategy.generate_intents(event, portfolio)
        orders: list[CoreOrder] = []
        for intent in intents:
            trade_intent_envelope = None
            if self.event_bus is not None:
                trade_intent_envelope = self.event_bus.publish(
                    TradingEventTopic.trade_intent,
                    intent,
                    causation_id=(strategy_input_envelope.event_id if strategy_input_envelope is not None else None),
                    correlation_id=(
                        strategy_input_envelope.correlation_id if strategy_input_envelope is not None else None
                    ),
                )
            order = self.execution_engine.submit_intent(intent, portfolio)
            orders.append(order)
            if self.event_bus is not None:
                self.event_bus.publish(
                    TradingEventTopic.order_state,
                    order_state_event(order),
                    causation_id=(trade_intent_envelope.event_id if trade_intent_envelope is not None else None),
                    correlation_id=(trade_intent_envelope.correlation_id if trade_intent_envelope is not None else None),
                )
        return TradingEngineResult(event=event, intents=intents, orders=orders)
