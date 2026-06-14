from pydantic import BaseModel, ConfigDict, Field

from app.trading_core.events import MarketEvent
from app.trading_core.portfolio import PortfolioState
from app.trading_core.strategy import Strategy, TradeIntent


class StrategyEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(min_length=1)
    intents: list[TradeIntent]


class StrategyEngine:
    def __init__(self, strategy_id: str, strategy: Strategy) -> None:
        normalized_strategy_id = strategy_id.strip()
        if not normalized_strategy_id:
            raise ValueError("strategy_id must not be empty")
        self.strategy_id = normalized_strategy_id
        self._strategy = strategy

    def generate_intents(self, event: MarketEvent, portfolio: PortfolioState) -> StrategyEngineResult:
        return StrategyEngineResult(
            strategy_id=self.strategy_id,
            intents=self._strategy.generate_intents(event, portfolio),
        )
