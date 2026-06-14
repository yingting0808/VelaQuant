from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny


class TradingEventTopic(str, Enum):
    market_event = "market_event"
    strategy_input = "strategy_input"
    trade_intent = "trade_intent"
    risk_decision = "risk_decision"
    order_state = "order_state"
    trade_explanation = "trade_explanation"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    topic: TradingEventTopic
    payload: SerializeAsAny[BaseModel]
    sequence: int
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    causation_id: UUID | None = None
    correlation_id: UUID


EventHandler = Callable[[EventEnvelope], None]


class RedisStreamClient(Protocol):
    def xadd(self, stream_name: str, fields: dict[str, str]):
        ...


class InMemoryEventBus:
    def __init__(self, initial_sequence: int = 0) -> None:
        self._history: list[EventEnvelope] = []
        self._handlers: dict[TradingEventTopic, list[EventHandler]] = {}
        self._initial_sequence = initial_sequence

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
        sequence = self._initial_sequence + len(self._history) + 1
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


class RedisStreamEventBus(InMemoryEventBus):
    def __init__(
        self,
        client: RedisStreamClient,
        stream_name: str = "trading:events",
        initial_sequence: int = 0,
    ) -> None:
        super().__init__(initial_sequence=initial_sequence)
        self.client = client
        self.stream_name = stream_name

    def publish(
        self,
        topic: TradingEventTopic,
        payload: BaseModel,
        causation_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> EventEnvelope:
        envelope = super().publish(topic, payload, causation_id=causation_id, correlation_id=correlation_id)
        self.client.xadd(self.stream_name, _stream_fields(envelope))
        return envelope


def build_event_bus(
    *,
    mode: str = "memory",
    redis_url: str | None = None,
    stream_name: str = "trading:events",
    initial_sequence: int = 0,
) -> InMemoryEventBus:
    if mode.strip().lower() != "redis":
        return InMemoryEventBus(initial_sequence=initial_sequence)

    if not redis_url:
        raise ValueError("redis_url is required when event bus mode is redis")

    from redis import Redis

    return RedisStreamEventBus(
        client=Redis.from_url(redis_url),
        stream_name=stream_name,
        initial_sequence=initial_sequence,
    )


def _stream_fields(envelope: EventEnvelope) -> dict[str, str]:
    return {
        "event_id": str(envelope.event_id),
        "event_type": envelope.topic.value,
        "topic": envelope.topic.value,
        "sequence": str(envelope.sequence),
        "published_at": envelope.published_at.isoformat(),
        "correlation_id": str(envelope.correlation_id),
        "causation_id": str(envelope.causation_id) if envelope.causation_id is not None else "",
        "payload_json": envelope.payload.model_dump_json(),
    }
