from pydantic import BaseModel, ConfigDict

from app.trading_core.events import MarketEvent
from app.trading_core.execution import CoreOrder, ExecutionEngine
from app.trading_core.portfolio import PortfolioState
from app.trading_core.risk import RiskEngine
from app.trading_core.strategy import Strategy, TradeIntent


class TradingEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: MarketEvent
    intents: list[TradeIntent]
    orders: list[CoreOrder]


class TradingEngine:
    def __init__(self, strategy: Strategy, risk_engine: RiskEngine) -> None:
        self.strategy = strategy
        self.execution_engine = ExecutionEngine(risk_engine)

    def process_event(self, event: MarketEvent, portfolio: PortfolioState) -> TradingEngineResult:
        intents = self.strategy.generate_intents(event, portfolio)
        orders = [self.execution_engine.submit_intent(intent, portfolio) for intent in intents]
        return TradingEngineResult(event=event, intents=intents, orders=orders)
