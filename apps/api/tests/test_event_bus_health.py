from app.core.config import Settings
from app.services.event_bus_health import get_event_bus_health


class FakeRedisClient:
    def __init__(self, length: int = 0, error: Exception | None = None) -> None:
        self.length = length
        self.error = error
        self.stream_names: list[str] = []

    def xlen(self, stream_name: str) -> int:
        self.stream_names.append(stream_name)
        if self.error is not None:
            raise self.error
        return self.length


def test_event_bus_health_reports_redis_stream_ready():
    client = FakeRedisClient(length=42)
    settings = Settings(event_bus_mode="redis", redis_url="redis://redis:6379/0", redis_stream_name="trading:events")

    health = get_event_bus_health(settings=settings, redis_client=client)

    assert health.ready is True
    assert health.mode == "redis"
    assert health.stream_name == "trading:events"
    assert health.stream_length == 42
    assert health.redis_available is True
    assert client.stream_names == ["trading:events"]


def test_event_bus_health_blocks_memory_mode_for_trading_readiness():
    settings = Settings(event_bus_mode="memory", redis_url="redis://redis:6379/0", redis_stream_name="trading:events")

    health = get_event_bus_health(settings=settings, redis_client=FakeRedisClient(length=42))

    assert health.ready is False
    assert health.mode == "memory"
    assert health.redis_available is False
    assert health.stream_length is None
    assert health.error == "event_bus_mode_not_redis"


def test_event_bus_health_reports_redis_stream_failure():
    settings = Settings(event_bus_mode="redis", redis_url="redis://redis:6379/0", redis_stream_name="trading:events")

    health = get_event_bus_health(settings=settings, redis_client=FakeRedisClient(error=ConnectionError("down")))

    assert health.ready is False
    assert health.redis_available is False
    assert health.stream_length is None
    assert health.error == "down"
