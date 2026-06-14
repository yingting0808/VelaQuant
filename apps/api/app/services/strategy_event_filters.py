import json

from app.domain.models import CoreEventLog


TRADE_EVENT_TOPICS = {
    "market_event",
    "strategy_input",
    "trade_intent",
    "trade_explanation",
    "risk_decision",
    "order_state",
}
MANUAL_OVERRIDE_STRATEGY_SUFFIX = ":manual_override"


def filter_strategy_trade_events(events: list[CoreEventLog]) -> list[CoreEventLog]:
    manual_override_correlations = manual_override_correlation_ids(events)
    return [
        event
        for event in events
        if event.topic in TRADE_EVENT_TOPICS and event.correlation_id not in manual_override_correlations
    ]


def manual_override_correlation_ids(events: list[CoreEventLog]) -> set[str]:
    return {
        event.correlation_id
        for event in events
        if _event_strategy_id(event).endswith(MANUAL_OVERRIDE_STRATEGY_SUFFIX)
    }


def _event_strategy_id(event: CoreEventLog) -> str:
    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""

    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    for value in (
        payload.get("order_strategy_id"),
        payload.get("strategy_id"),
        metadata.get("order_strategy_id"),
        metadata.get("strategy_id"),
    ):
        if isinstance(value, str):
            return value
    return ""
