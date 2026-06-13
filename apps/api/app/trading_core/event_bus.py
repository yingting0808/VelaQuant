from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TradingEventTopic(str, Enum):
    market_event = "market_event"
    strategy_input = "strategy_input"
    trade_intent = "trade_intent"
    order_state = "order_state"
    trade_explanation = "trade_explanation"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    topic: TradingEventTopic
    payload: BaseModel
    sequence: int
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    causation_id: UUID | None = None
    correlation_id: UUID


EventHandler = Callable[[EventEnvelope], None]


class InMemoryEventBus:
    def __init__(self) -> None:
        self._history: list[EventEnvelope] = []
        self._handlers: dict[TradingEventTopic, list[EventHandler]] = {}

    @property
    def history(self) -> list[EventEnvelope]:
        return list(self._history)

    def subscribe(self, topic: TradingEventTopic, handler: EventHandler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    def publish(
        self,
        topic: TradingEventTopic,
        payload: BaseModel,
        causation_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> EventEnvelope:
        sequence = len(self._history) + 1
        envelope = EventEnvelope(
            topic=topic,
            payload=payload,
            sequence=sequence,
            causation_id=causation_id,
            correlation_id=correlation_id or uuid4(),
        )
        self._history.append(envelope)
        for handler in self._handlers.get(topic, []):
            handler(envelope)
        return envelope
