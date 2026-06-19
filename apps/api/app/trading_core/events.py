from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.trading_core.portfolio import PortfolioState


class EventSource(str, Enum):
    market_data = "market_data"
    news = "news"
    sec_filing = "sec_filing"
    analyst = "analyst"
    macro = "macro"
    ai_structured = "ai_structured"
    manual = "manual"


class MarketEventType(str, Enum):
    price_move = "price_move"
    earnings = "earnings"
    filing = "filing"
    news = "news"
    analyst_rating = "analyst_rating"
    macro = "macro"
    risk = "risk"


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class MarketEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    source: EventSource
    event_type: MarketEventType
    ticker: str = Field(min_length=1)
    occurred_at: datetime
    summary: str = Field(min_length=1)
    sentiment: Sentiment = Sentiment.neutral
    confidence: float = Field(ge=0, le=1)
    impact_score: float = Field(ge=0, le=1)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("summary must not be empty")
        return stripped


class StrategyInputEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_event: MarketEvent
    portfolio: PortfolioState


class TradeExplanationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    candidate_id: UUID | None = None
    decision: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    evidence_items: list[dict[str, str | None]] = Field(default_factory=list)
    backtest: dict[str, str | bool | None] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_explanation_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized
