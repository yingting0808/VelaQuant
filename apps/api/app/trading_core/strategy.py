from enum import Enum
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.trading_core.events import MarketEvent, Sentiment
from app.trading_core.portfolio import PortfolioState


class TradeIntentSide(str, Enum):
    buy = "buy"
    sell = "sell"


class TradeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_id: UUID = Field(default_factory=uuid4)
    ticker: str = Field(min_length=1)
    side: TradeIntentSide
    notional: float = Field(gt=0)
    reason: str = Field(min_length=1)
    source_event_id: UUID | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be empty")
        return stripped


class Strategy(Protocol):
    def generate_intents(self, event: MarketEvent, portfolio: PortfolioState) -> list[TradeIntent]:
        ...


class DeterministicWatchlistStrategy:
    def __init__(
        self,
        watchlist: list[str],
        notional: float,
        min_confidence: float = 0.7,
        min_impact_score: float = 0.6,
    ) -> None:
        self.watchlist = {ticker.strip().upper() for ticker in watchlist if ticker.strip()}
        self.notional = notional
        self.min_confidence = min_confidence
        self.min_impact_score = min_impact_score

    def generate_intents(self, event: MarketEvent, portfolio: PortfolioState) -> list[TradeIntent]:
        if event.ticker not in self.watchlist:
            return []
        if event.sentiment != Sentiment.positive:
            return []
        if event.confidence < self.min_confidence or event.impact_score < self.min_impact_score:
            return []
        if portfolio.cash <= 0:
            return []

        notional = min(self.notional, portfolio.cash)
        return [
            TradeIntent(
                intent_id=uuid5(NAMESPACE_URL, f"{event.event_id}:{event.ticker}:buy:{notional:.2f}"),
                ticker=event.ticker,
                side=TradeIntentSide.buy,
                notional=notional,
                reason=f"{event.ticker} positive {event.event_type.value} event: {event.summary}",
                source_event_id=event.event_id,
            )
        ]
