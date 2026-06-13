import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperRun
from app.services.workspace import get_or_create_default_workspace


class EventLedgerTopicCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    count: int


class EventLedgerReplayChain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    ticker: str | None
    topics: list[str]
    order_states: list[str]
    terminal_state: str | None
    event_count: int


class EventLedgerReplay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    event_count: int
    chain_count: int
    chains: list[EventLedgerReplayChain]


class EventLedgerStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_event_count: int
    latest_run_id: UUID | None
    latest_run_status: str | None
    latest_run_event_count: int
    latest_topic_counts: list[EventLedgerTopicCount]
    latest_correlation_count: int
    replay_ready: bool
    warnings: list[str]
    summary: str
    latest_replay: EventLedgerReplay | None


def get_event_ledger_status(session: Session) -> EventLedgerStatus:
    workspace = get_or_create_default_workspace(session)
    team_id = workspace.team.id
    total_event_count = len(session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id)).all())
    latest_run = session.exec(
        select(PaperRun)
        .where(PaperRun.team_id == team_id)
        .order_by(PaperRun.started_at.desc())
    ).first()
    if latest_run is None:
        warnings = ["no_paper_runs"]
        if total_event_count == 0:
            warnings.append("missing_core_events")
        return EventLedgerStatus(
            total_event_count=total_event_count,
            latest_run_id=None,
            latest_run_status=None,
            latest_run_event_count=0,
            latest_topic_counts=[],
            latest_correlation_count=0,
            replay_ready=False,
            warnings=warnings,
            summary="No paper runs found; event replay is not available.",
            latest_replay=None,
        )

    latest_events = _run_events(session, latest_run.id)
    latest_replay = _replay_from_events(latest_run.id, latest_events) if latest_events else None
    warnings: list[str] = []
    if total_event_count == 0:
        warnings.append("missing_core_events")
    if not latest_events:
        warnings.append("latest_run_has_no_events")
    return EventLedgerStatus(
        total_event_count=total_event_count,
        latest_run_id=latest_run.id,
        latest_run_status=latest_run.status.value,
        latest_run_event_count=len(latest_events),
        latest_topic_counts=_topic_counts(latest_events),
        latest_correlation_count=len({event.correlation_id for event in latest_events}),
        replay_ready=latest_replay is not None,
        warnings=warnings,
        summary=_summary(latest_run, latest_replay),
        latest_replay=latest_replay,
    )


def replay_paper_run(session: Session, run_id: UUID) -> EventLedgerReplay:
    return _replay_from_events(run_id, _run_events(session, run_id))


def _run_events(session: Session, run_id: UUID) -> list[CoreEventLog]:
    return list(
        session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.run_id == run_id)
            .order_by(CoreEventLog.sequence, CoreEventLog.published_at)
        ).all()
    )


def _replay_from_events(run_id: UUID, events: list[CoreEventLog]) -> EventLedgerReplay:
    grouped: dict[str, list[CoreEventLog]] = {}
    for event in events:
        grouped.setdefault(event.correlation_id, []).append(event)

    chains = []
    for correlation_id, chain_events in grouped.items():
        ordered_events = sorted(chain_events, key=lambda event: (event.sequence, event.published_at))
        order_states = [_event_state(event) for event in ordered_events if event.topic == "order_state"]
        order_states = [state for state in order_states if state is not None]
        chains.append(
            EventLedgerReplayChain(
                correlation_id=correlation_id,
                ticker=_chain_ticker(ordered_events),
                topics=[event.topic for event in ordered_events],
                order_states=order_states,
                terminal_state=order_states[-1] if order_states else None,
                event_count=len(ordered_events),
            )
        )
    chains.sort(key=lambda chain: (not bool(chain.order_states), chain.ticker or "", chain.correlation_id))
    return EventLedgerReplay(
        run_id=run_id,
        event_count=len(events),
        chain_count=len(chains),
        chains=chains,
    )


def _topic_counts(events: list[CoreEventLog]) -> list[EventLedgerTopicCount]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.topic] = counts.get(event.topic, 0) + 1
    return [EventLedgerTopicCount(topic=topic, count=counts[topic]) for topic in sorted(counts)]


def _chain_ticker(events: list[CoreEventLog]) -> str | None:
    for event in events:
        payload = _event_payload(event)
        ticker = payload.get("ticker")
        if isinstance(ticker, str) and ticker:
            return ticker.upper()
        nested = payload.get("market_event")
        if isinstance(nested, dict):
            nested_ticker = nested.get("ticker")
            if isinstance(nested_ticker, str) and nested_ticker:
                return nested_ticker.upper()
    return None


def _event_state(event: CoreEventLog) -> str | None:
    payload = _event_payload(event)
    state = payload.get("state")
    if isinstance(state, str) and state:
        return state
    current_state = payload.get("current_state")
    if isinstance(current_state, str) and current_state:
        return current_state
    return None


def _event_payload(event: CoreEventLog) -> dict:
    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(run: PaperRun, replay: EventLedgerReplay | None) -> str:
    if replay is None:
        return f"Latest paper run is {run.status.value} and has no replayable core events."
    return (
        f"Latest paper run is {run.status.value} with "
        f"{replay.event_count} replayable core events across {replay.chain_count} chains."
    )
