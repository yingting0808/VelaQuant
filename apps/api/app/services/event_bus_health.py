from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.core.config import Settings, get_settings


class RedisStreamHealthClient(Protocol):
    def xlen(self, stream_name: str) -> int:
        ...


class EventBusHealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    stream_name: str
    redis_url_configured: bool
    redis_available: bool
    stream_length: int | None
    ready: bool
    error: str | None
    summary: str


def get_event_bus_health(
    *,
    settings: Settings | None = None,
    redis_client: RedisStreamHealthClient | None = None,
) -> EventBusHealthPayload:
    resolved_settings = settings or get_settings()
    mode = resolved_settings.event_bus_mode.strip().lower()
    stream_name = resolved_settings.redis_stream_name
    redis_url_configured = bool(resolved_settings.redis_url)
    if mode != "redis":
        return EventBusHealthPayload(
            mode=mode,
            stream_name=stream_name,
            redis_url_configured=redis_url_configured,
            redis_available=False,
            stream_length=None,
            ready=False,
            error="event_bus_mode_not_redis",
            summary=f"Event bus mode is {mode}; Redis Streams is required for trading readiness.",
        )
    if not redis_url_configured:
        return EventBusHealthPayload(
            mode=mode,
            stream_name=stream_name,
            redis_url_configured=False,
            redis_available=False,
            stream_length=None,
            ready=False,
            error="redis_url_not_configured",
            summary="Redis Streams event bus is configured, but redis_url is missing.",
        )

    try:
        client = redis_client or _build_redis_client(resolved_settings.redis_url)
        stream_length = int(client.xlen(stream_name))
    except Exception as error:  # pragma: no cover - exact redis exceptions vary by client/version.
        return EventBusHealthPayload(
            mode=mode,
            stream_name=stream_name,
            redis_url_configured=True,
            redis_available=False,
            stream_length=None,
            ready=False,
            error=str(error),
            summary=f"Redis Streams event bus is not available: {error}.",
        )

    return EventBusHealthPayload(
        mode=mode,
        stream_name=stream_name,
        redis_url_configured=True,
        redis_available=True,
        stream_length=stream_length,
        ready=True,
        error=None,
        summary=f"Redis Streams event bus is available on {stream_name} with {stream_length} events.",
    )


def _build_redis_client(redis_url: str) -> RedisStreamHealthClient:
    from redis import Redis

    return Redis.from_url(redis_url)
