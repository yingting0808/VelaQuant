import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.domain.models import CoreEventLog, PaperRun
from app.services.market_calendar import current_market_trading_day
from app.services.workspace import get_or_create_default_workspace

EvidenceQuality = Literal["unknown", "real_market_data", "mock_data", "deterministic_research_series", "mixed"]


class EventLedgerTopicCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    count: int


class EventLedgerTradeExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str | None = None
    strategy_id: str | None = None
    candidate_id: str | None = None
    decision: str | None = None
    explanation: str | None = None
    evidence: list[str] = Field(default_factory=list)
    evidence_items: list[dict[str, str | None]] = Field(default_factory=list)
    backtest: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EventLedgerReplayChain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    ticker: str | None
    topics: list[str]
    order_states: list[str]
    terminal_state: str | None
    event_count: int
    integrity_warnings: list[str] = Field(default_factory=list)
    trade_explanation: EventLedgerTradeExplanation | None = None


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
    latest_run_trading_day: str | None = None
    latest_run_status: str | None
    latest_run_event_count: int
    latest_topic_counts: list[EventLedgerTopicCount]
    latest_correlation_count: int
    integrity_ready: bool = False
    integrity_warnings: list[str] = Field(default_factory=list)
    traceable_chain_count: int = 0
    complete_order_chain_count: int = 0
    broken_chain_count: int = 0
    traceability_ratio: float = 0.0
    replay_ready: bool
    warnings: list[str]
    summary: str
    latest_replay: EventLedgerReplay | None


class MarketEventTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    topic: str
    sequence: int
    causation_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class MarketEventTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    run_id: UUID | None
    trading_day: str | None
    published_at: datetime
    correlation_id: str
    ticker: str | None
    strategy_id: str | None
    event_type: str | None
    summary: str | None
    confidence: float | None
    impact_score: float | None
    source: str | None
    evidence_quality: EvidenceQuality = "unknown"
    uses_real_market_evidence: bool = False
    topics: list[str]
    trade_intent_side: str | None = None
    trade_intent_reason: str | None = None
    risk_decision: str | None = None
    risk_reason: str | None = None
    order_state: str | None = None
    explanation: str | None = None
    evidence: list[str] = Field(default_factory=list)
    evidence_items: list[dict[str, str | None]] = Field(default_factory=list)
    chain_events: list[MarketEventTraceEvent] = Field(default_factory=list)


class MarketEventTracePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_event_count: int
    filtered_event_count: int
    events: list[MarketEventTrace]
    summary: str


def get_event_ledger_status(
    session: Session,
    *,
    as_of_trading_day: str | None = None,
) -> EventLedgerStatus:
    workspace = get_or_create_default_workspace(session)
    team_id = workspace.team.id
    as_of_trading_day = as_of_trading_day or _current_trading_day()
    total_event_count = len(session.exec(select(CoreEventLog).where(CoreEventLog.team_id == team_id)).all())
    latest_run, latest_events = _latest_event_ledger_run(session, team_id=team_id, as_of_trading_day=as_of_trading_day)
    if latest_run is None:
        warnings = ["no_paper_runs"]
        if total_event_count == 0:
            warnings.append("missing_core_events")
        return EventLedgerStatus(
            total_event_count=total_event_count,
            latest_run_id=None,
            latest_run_trading_day=None,
            latest_run_status=None,
            latest_run_event_count=0,
            latest_topic_counts=[],
            latest_correlation_count=0,
            integrity_ready=False,
            integrity_warnings=["missing_core_events"],
            replay_ready=False,
            warnings=warnings,
            summary="No paper runs found; event replay is not available.",
            latest_replay=None,
        )

    latest_replay = _replay_from_events(latest_run.id, latest_events) if latest_events else None
    integrity_warnings = _replay_integrity_warnings(latest_replay)
    traceability = _traceability_metrics(latest_replay)
    integrity_ready = latest_replay is not None and not integrity_warnings
    warnings: list[str] = []
    if total_event_count == 0:
        warnings.append("missing_core_events")
    if not latest_events:
        warnings.append("latest_run_has_no_events")
    warnings.extend(warning for warning in integrity_warnings if warning not in warnings)
    return EventLedgerStatus(
        total_event_count=total_event_count,
        latest_run_id=latest_run.id,
        latest_run_trading_day=latest_run.trading_day,
        latest_run_status=latest_run.status.value,
        latest_run_event_count=len(latest_events),
        latest_topic_counts=_topic_counts(latest_events),
        latest_correlation_count=len({event.correlation_id for event in latest_events}),
        integrity_ready=integrity_ready,
        integrity_warnings=integrity_warnings,
        traceable_chain_count=traceability["traceable_chain_count"],
        complete_order_chain_count=traceability["complete_order_chain_count"],
        broken_chain_count=traceability["broken_chain_count"],
        traceability_ratio=traceability["traceability_ratio"],
        replay_ready=integrity_ready,
        warnings=warnings,
        summary=_summary(latest_run, latest_replay),
        latest_replay=latest_replay,
    )


def list_market_event_traces(
    session: Session,
    *,
    ticker: str | None = None,
    strategy_id: str | None = None,
    limit: int = 50,
) -> MarketEventTracePayload:
    workspace = get_or_create_default_workspace(session)
    team_id = workspace.team.id
    normalized_ticker = ticker.strip().upper() if ticker else None
    normalized_strategy_id = strategy_id.strip() if strategy_id else None
    bounded_limit = max(1, min(limit, 200))
    events = list(
        session.exec(
            select(CoreEventLog)
            .where(CoreEventLog.team_id == team_id)
            .order_by(CoreEventLog.published_at.desc(), CoreEventLog.sequence.desc())
        ).all()
    )
    market_events = [event for event in events if event.topic == "market_event"]
    events_by_correlation: dict[str, list[CoreEventLog]] = {}
    run_trading_days = _run_trading_days(session, {event.run_id for event in market_events if event.run_id is not None})
    for event in events:
        events_by_correlation.setdefault(event.correlation_id, []).append(event)

    traces: list[MarketEventTrace] = []
    for event in market_events:
        chain = sorted(
            events_by_correlation.get(event.correlation_id, []),
            key=lambda item: (item.sequence, item.published_at),
        )
        trace = _market_event_trace(event, chain, run_trading_days=run_trading_days)
        if normalized_ticker and trace.ticker != normalized_ticker:
            continue
        if normalized_strategy_id and trace.strategy_id != normalized_strategy_id:
            continue
        if trace.evidence_quality != "real_market_data":
            continue
        traces.append(trace)

    return MarketEventTracePayload(
        total_event_count=len(market_events),
        filtered_event_count=len(traces),
        events=traces[:bounded_limit],
        summary=_market_event_trace_summary(len(market_events), len(traces[:bounded_limit])),
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
    event_ids = {event.event_id for event in events}
    event_correlation_by_id = {event.event_id: event.correlation_id for event in events}
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
                trade_explanation=_chain_trade_explanation(ordered_events),
                integrity_warnings=_chain_integrity_warnings(
                    ordered_events,
                    event_ids=event_ids,
                    event_correlation_by_id=event_correlation_by_id,
                ),
            )
        )
    chains.sort(key=lambda chain: (not bool(chain.order_states), chain.ticker or "", chain.correlation_id))
    return EventLedgerReplay(
        run_id=run_id,
        event_count=len(events),
        chain_count=len(chains),
        chains=chains,
    )


def _latest_event_ledger_run(
    session: Session,
    *,
    team_id: UUID,
    as_of_trading_day: str,
) -> tuple[PaperRun | None, list[CoreEventLog]]:
    runs = list(
        session.exec(
            select(PaperRun)
            .where(PaperRun.team_id == team_id)
            .where(PaperRun.trading_day <= as_of_trading_day)
            .order_by(PaperRun.started_at.desc())
        ).all()
    )
    fallback: tuple[PaperRun | None, list[CoreEventLog]] = (None, [])
    for index, run in enumerate(runs):
        events = _run_events(session, run.id)
        if index == 0:
            fallback = (run, events)
        if _has_trade_replay_events(events):
            return run, events
    return fallback


def _has_trade_replay_events(events: list[CoreEventLog]) -> bool:
    topics = {event.topic for event in events}
    return bool(topics & {"market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"})


def _replay_integrity_warnings(replay: EventLedgerReplay | None) -> list[str]:
    if replay is None:
        return []
    warnings: list[str] = []
    for chain in replay.chains:
        for warning in chain.integrity_warnings:
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _traceability_metrics(replay: EventLedgerReplay | None) -> dict[str, int | float]:
    if replay is None:
        return {
            "traceable_chain_count": 0,
            "complete_order_chain_count": 0,
            "broken_chain_count": 0,
            "traceability_ratio": 0.0,
        }
    complete_order_chains = [chain for chain in replay.chains if _is_complete_order_chain(chain)]
    broken_order_chains = [chain for chain in replay.chains if _is_broken_order_chain(chain)]
    broken_chain_count = len(broken_order_chains)
    traceable_chain_count = len(complete_order_chains) + broken_chain_count
    traceability_ratio = (
        round(len(complete_order_chains) / traceable_chain_count, 4)
        if traceable_chain_count
        else 0.0
    )
    return {
        "traceable_chain_count": traceable_chain_count,
        "complete_order_chain_count": len(complete_order_chains),
        "broken_chain_count": broken_chain_count,
        "traceability_ratio": traceability_ratio,
    }


def _is_broken_order_chain(chain: EventLedgerReplayChain) -> bool:
    topics = set(chain.topics)
    return bool(topics & {"risk_decision", "order_state"}) and not _is_complete_order_chain(chain)


def _is_complete_order_chain(chain: EventLedgerReplayChain) -> bool:
    return (
        {"market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"}.issubset(set(chain.topics))
        and not chain.integrity_warnings
    )


def _chain_integrity_warnings(
    events: list[CoreEventLog],
    *,
    event_ids: set[str],
    event_correlation_by_id: dict[str, str],
) -> list[str]:
    topics = {event.topic for event in events}
    warnings: list[str] = []
    required_topics: set[str] = set()

    if "order_state" in topics:
        required_topics = {"market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"}
    elif "risk_decision" in topics:
        required_topics = {"market_event", "strategy_input", "trade_intent", "risk_decision"}
    elif "trade_intent" in topics:
        required_topics = {"market_event", "strategy_input", "trade_intent"}

    for topic in sorted(required_topics - topics):
        warnings.append(f"chain_missing_{topic}")

    for event in events:
        if event.causation_id is None:
            continue
        if event.causation_id not in event_ids:
            _append_unique(warnings, "broken_causation_reference")
            continue
        if event_correlation_by_id.get(event.causation_id) != event.correlation_id:
            _append_unique(warnings, "broken_causation_reference")
    return warnings


def _append_unique(values: list[str], item: str) -> None:
    if item not in values:
        values.append(item)


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


def _chain_trade_explanation(events: list[CoreEventLog]) -> EventLedgerTradeExplanation | None:
    for event in reversed(events):
        if event.topic != "trade_explanation":
            continue
        payload = _event_payload(event)
        evidence = payload.get("evidence")
        backtest = payload.get("backtest")
        return EventLedgerTradeExplanation(
            ticker=_optional_str(payload.get("ticker")),
            strategy_id=_optional_str(payload.get("strategy_id")),
            candidate_id=_optional_str(payload.get("candidate_id")),
            decision=_optional_str(payload.get("decision")),
            explanation=_optional_str(payload.get("explanation")),
            evidence=[item for item in evidence if isinstance(item, str)] if isinstance(evidence, list) else [],
            evidence_items=_evidence_items_payload(payload.get("evidence_items")),
            backtest=backtest if isinstance(backtest, dict) else {},
        )
    return None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _evidence_items_payload(value: object) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str | None]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "ticker": _optional_str(item.get("ticker")),
                "title": _optional_str(item.get("title")),
                "summary": _optional_str(item.get("summary")),
                "source": _optional_str(item.get("source")),
                "source_url": _optional_str(item.get("source_url")),
                "observed_at": _optional_str(item.get("observed_at")),
                "form": _optional_str(item.get("form")),
                "filing_date": _optional_str(item.get("filing_date")),
                "accession_number": _optional_str(item.get("accession_number")),
            }
        )
    return items


def _event_payload(event: CoreEventLog) -> dict:
    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_trading_days(session: Session, run_ids: set[UUID]) -> dict[UUID, str]:
    if not run_ids:
        return {}
    runs = list(session.exec(select(PaperRun).where(PaperRun.id.in_(run_ids))).all())
    return {run.id: run.trading_day for run in runs}


def _market_event_trace(
    event: CoreEventLog,
    chain: list[CoreEventLog],
    *,
    run_trading_days: dict[UUID, str],
) -> MarketEventTrace:
    payload = _event_payload(event)
    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    explanation = _chain_trade_explanation(chain)
    trade_intent_payload = _latest_topic_payload(chain, "trade_intent")
    risk_payload = _latest_topic_payload(chain, "risk_decision")
    order_payload = _latest_topic_payload(chain, "order_state")
    evidence_items = _evidence_items_payload(payload.get("evidence_items")) or (
        explanation.evidence_items if explanation else []
    )
    evidence_sources = _trace_evidence_sources(payload, evidence_items, explanation)
    evidence_quality = _evidence_quality(evidence_sources)
    return MarketEventTrace(
        event_id=event.event_id,
        run_id=event.run_id,
        trading_day=run_trading_days.get(event.run_id) if event.run_id is not None else None,
        published_at=event.published_at,
        correlation_id=event.correlation_id,
        ticker=_payload_ticker(payload),
        strategy_id=_optional_str(metadata.get("strategy_id")) or (explanation.strategy_id if explanation else None),
        event_type=_optional_str(payload.get("event_type")),
        summary=_optional_str(payload.get("summary")),
        confidence=_optional_float(payload.get("confidence")),
        impact_score=_optional_float(payload.get("impact_score")),
        source=_optional_str(metadata.get("source")) or _optional_str(payload.get("source")),
        evidence_quality=evidence_quality,
        uses_real_market_evidence=_has_real_market_evidence(evidence_sources),
        topics=[item.topic for item in chain],
        trade_intent_side=_optional_str(trade_intent_payload.get("side")),
        trade_intent_reason=_optional_str(trade_intent_payload.get("reason")),
        risk_decision=_risk_decision_label(risk_payload),
        risk_reason=_optional_str(risk_payload.get("reason")),
        order_state=_optional_str(order_payload.get("state")) or _optional_str(order_payload.get("current_state")),
        explanation=explanation.explanation if explanation else None,
        evidence=explanation.evidence if explanation else [],
        evidence_items=evidence_items,
        chain_events=[
            MarketEventTraceEvent(
                event_id=item.event_id,
                topic=item.topic,
                sequence=item.sequence,
                causation_id=item.causation_id,
                payload=_event_payload(item),
            )
            for item in chain
        ],
    )


def _trace_evidence_sources(
    payload: dict,
    evidence_items: list[dict[str, str | None]],
    explanation: EventLedgerTradeExplanation | None,
) -> list[str]:
    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    sources: list[str] = []
    for value in [
        payload.get("source"),
        metadata.get("source"),
        metadata.get("price_source"),
        metadata.get("data_source"),
        metadata.get("quote_source"),
    ]:
        if isinstance(value, str) and value.strip():
            sources.append(value)
    for item in evidence_items:
        for key in ("source", "source_url"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                sources.append(value)
    if explanation:
        for item in explanation.evidence:
            if not isinstance(item, str):
                continue
            if item.startswith("source=") or item.startswith("quote_source=") or item.startswith("data_source="):
                sources.append(item.split("=", 1)[1])
    return sources


def _evidence_quality(sources: list[str]) -> EvidenceQuality:
    if not sources:
        return "unknown"
    has_real = any(_is_real_market_source(source) for source in sources)
    has_mock = any(_is_mock_source(source) for source in sources)
    has_deterministic = any(_is_deterministic_source(source) for source in sources)
    active_kinds = sum(1 for value in (has_real, has_mock, has_deterministic) if value)
    if active_kinds > 1:
        return "mixed"
    if has_real:
        return "real_market_data"
    if has_mock:
        return "mock_data"
    if has_deterministic:
        return "deterministic_research_series"
    return "unknown"


def _has_real_market_evidence(sources: list[str]) -> bool:
    return any(_is_real_market_source(source) for source in sources)


def _is_real_market_source(source: str) -> bool:
    normalized = source.strip().lower()
    return normalized.startswith(("openbb_", "alpaca", "polygon", "sec_edgar")) or normalized == "mixed_real_market_data"


def _is_mock_source(source: str) -> bool:
    normalized = source.strip().lower()
    return normalized.startswith("mock") or normalized.startswith("mock://") or ":mock" in normalized


def _is_deterministic_source(source: str) -> bool:
    return source.strip().lower() == "deterministic_research_series"


def _latest_topic_payload(events: list[CoreEventLog], topic: str) -> dict:
    for event in reversed(events):
        if event.topic == topic:
            return _event_payload(event)
    return {}


def _payload_ticker(payload: dict) -> str | None:
    ticker = payload.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()
    nested = payload.get("market_event")
    if isinstance(nested, dict):
        nested_ticker = nested.get("ticker")
        if isinstance(nested_ticker, str) and nested_ticker.strip():
            return nested_ticker.strip().upper()
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _risk_decision_label(payload: dict) -> str | None:
    approved = payload.get("approved")
    if isinstance(approved, bool):
        return "approved" if approved else "rejected"
    status = payload.get("status")
    if isinstance(status, str) and status:
        return status
    code = payload.get("code")
    if isinstance(code, str) and code:
        return code
    return None


def _market_event_trace_summary(total: int, visible: int) -> str:
    if total == 0:
        return "No market events have been persisted yet."
    return f"Showing {visible} real market events from {total} persisted market events."


def _summary(run: PaperRun, replay: EventLedgerReplay | None) -> str:
    if replay is None:
        return f"Latest paper run is {run.status.value} and has no replayable core events."
    return (
        f"Latest paper run is {run.status.value} with "
        f"{replay.event_count} replayable core events across {replay.chain_count} chains."
    )


def _current_trading_day() -> str:
    return current_market_trading_day()
