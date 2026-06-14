import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.data.providers.base import MarketDataProvider
from app.domain.models import StrategyCompetitionEntry, StrategyCompetitionSnapshot, utc_now
from app.services.market_calendar import current_market_trading_day
from app.services.strategy_registry import StrategyRegistryEntry, StrategyRegistryPayload, get_strategy_registry
from app.services.workspace import get_or_create_default_workspace


MIN_COMPETITION_FILLED_ORDERS = 30
ALLOCATABLE_READINESS = {"watch", "paper_ready"}


class StrategyCompetitionEntryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    name: str
    version: str
    source: str
    execution_mode: str
    status: str
    rank: int
    ranking_score: float
    allocation_weight: float
    eligible_for_allocation: bool
    recommended_action: str
    blockers: list[str]
    readiness: str
    promotion_gate: str
    sample_size: int
    filled_order_count: int
    observed_pnl: float
    primary_regime: str
    signal_quality_score: float
    supports_live: bool
    supports_hot_swap: bool


class StrategyCompetitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trading_day: str
    status: str
    active_strategy_id: str
    selected_strategy_id: str | None
    strategy_count: int
    allocatable_strategy_count: int
    competition_ready: bool
    entries: list[StrategyCompetitionEntryPayload]
    summary: str


class StrategyCompetitionSnapshotPayload(StrategyCompetitionPayload):
    id: UUID
    team_id: UUID
    created_at: str
    updated_at: str


class StrategyCompetitionSnapshotHistoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_count: int
    latest: StrategyCompetitionSnapshotPayload | None
    items: list[StrategyCompetitionSnapshotPayload]
    summary: str


def get_strategy_competition(
    session: Session,
    *,
    provider: MarketDataProvider | None = None,
    trading_day: str | None = None,
) -> StrategyCompetitionPayload:
    return build_strategy_competition(
        registry=get_strategy_registry(session, provider=provider),
        trading_day=trading_day or current_market_trading_day(),
    )


def build_strategy_competition(
    *,
    registry: StrategyRegistryPayload,
    trading_day: str,
) -> StrategyCompetitionPayload:
    ranked_entries = _competition_entries(registry.entries)
    allocatable = [entry for entry in ranked_entries if entry.eligible_for_allocation]
    _apply_allocation_weights(allocatable)
    entries = sorted(ranked_entries, key=lambda entry: (-entry.ranking_score, entry.strategy_id))
    selected_strategy_id = allocatable[0].strategy_id if allocatable else None
    competition_ready = len(allocatable) >= 2
    status = "allocation_ready" if allocatable else "collecting"
    return StrategyCompetitionPayload(
        trading_day=trading_day,
        status=status,
        active_strategy_id=registry.active_strategy_id,
        selected_strategy_id=selected_strategy_id,
        strategy_count=len(entries),
        allocatable_strategy_count=len(allocatable),
        competition_ready=competition_ready,
        entries=entries,
        summary=_summary(len(entries), len(allocatable), selected_strategy_id, competition_ready),
    )


def record_strategy_competition_snapshot(
    session: Session,
    *,
    provider: MarketDataProvider | None = None,
    team_id: UUID | None = None,
    trading_day: str | None = None,
) -> StrategyCompetitionSnapshotPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    payload = get_strategy_competition(session, provider=provider, trading_day=trading_day)
    return record_strategy_competition_snapshot_from_payload(session, team_id=team_id, payload=payload)


def record_strategy_competition_snapshot_from_payload(
    session: Session,
    *,
    team_id: UUID,
    payload: StrategyCompetitionPayload,
) -> StrategyCompetitionSnapshotPayload:
    snapshot = session.exec(
        select(StrategyCompetitionSnapshot).where(
            StrategyCompetitionSnapshot.team_id == team_id,
            StrategyCompetitionSnapshot.trading_day == payload.trading_day,
        )
    ).first()
    if snapshot is None:
        snapshot = StrategyCompetitionSnapshot(team_id=team_id, trading_day=payload.trading_day)
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)

    snapshot.status = payload.status
    snapshot.selected_strategy_id = payload.selected_strategy_id
    snapshot.strategy_count = payload.strategy_count
    snapshot.allocatable_strategy_count = payload.allocatable_strategy_count
    snapshot.competition_ready = payload.competition_ready
    snapshot.updated_at = utc_now()
    session.add(snapshot)

    for entry in session.exec(
        select(StrategyCompetitionEntry).where(StrategyCompetitionEntry.snapshot_id == snapshot.id)
    ).all():
        session.delete(entry)
    session.flush()
    for entry_payload in payload.entries:
        session.add(_entry_row(snapshot.id, team_id, entry_payload))
    session.commit()
    session.refresh(snapshot)
    return _snapshot_payload(session, snapshot, payload.active_strategy_id)


def get_strategy_competition_snapshots(
    session: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 20,
) -> StrategyCompetitionSnapshotHistoryPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    snapshots = list(
        session.exec(
            select(StrategyCompetitionSnapshot)
            .where(StrategyCompetitionSnapshot.team_id == team_id)
            .order_by(StrategyCompetitionSnapshot.trading_day.desc(), StrategyCompetitionSnapshot.updated_at.desc())
        ).all()
    )
    items = [_snapshot_payload(session, snapshot, _active_strategy_id(snapshot)) for snapshot in snapshots[:limit]]
    latest = items[0] if items else None
    return StrategyCompetitionSnapshotHistoryPayload(
        snapshot_count=len(snapshots),
        latest=latest,
        items=items,
        summary=_history_summary(len(snapshots), latest),
    )


def _competition_entries(entries: list[StrategyRegistryEntry]) -> list[StrategyCompetitionEntryPayload]:
    return [
        StrategyCompetitionEntryPayload(
            strategy_id=entry.strategy_id,
            name=entry.name,
            version=entry.version,
            source=entry.source,
            execution_mode=entry.execution_mode,
            status=entry.status,
            rank=entry.rank,
            ranking_score=round(entry.ranking_score, 2),
            allocation_weight=0.0,
            eligible_for_allocation=_eligible_for_allocation(entry),
            recommended_action=_recommended_action(entry),
            blockers=_blockers(entry),
            readiness=entry.readiness,
            promotion_gate=entry.promotion_gate,
            sample_size=entry.sample_size,
            filled_order_count=entry.filled_order_count,
            observed_pnl=round(entry.observed_pnl, 2),
            primary_regime=entry.primary_regime,
            signal_quality_score=round(entry.signal_quality_score, 4),
            supports_live=entry.supports_live,
            supports_hot_swap=entry.supports_hot_swap,
        )
        for entry in entries
    ]


def _eligible_for_allocation(entry: StrategyRegistryEntry) -> bool:
    return not _blockers(entry)


def _blockers(entry: StrategyRegistryEntry) -> list[str]:
    blockers: list[str] = []
    if entry.source != "paper_core" or entry.execution_mode != "paper":
        blockers.append("not_connected_to_paper_runtime")
    if entry.status != "active":
        blockers.append("strategy_not_active")
    if entry.readiness not in ALLOCATABLE_READINESS:
        blockers.append("readiness_not_allocatable")
    if entry.filled_order_count < MIN_COMPETITION_FILLED_ORDERS:
        blockers.append("filled_order_sample")
    if entry.ranking_score <= 0:
        blockers.append("ranking_score_unavailable")
    if not entry.supports_hot_swap:
        blockers.append("hot_swap_not_supported")
    return blockers


def _recommended_action(entry: StrategyRegistryEntry) -> str:
    if entry.readiness == "negative_expectancy":
        return "kill_review"
    if _eligible_for_allocation(entry):
        return "allocate_paper_capital"
    if entry.source == "lean_catalog" and entry.readiness == "backtest_promising":
        return "connect_to_paper_runtime"
    if entry.source == "lean_catalog":
        return "keep_in_lab"
    return "collect_more_evidence"


def _apply_allocation_weights(entries: list[StrategyCompetitionEntryPayload]) -> None:
    score_sum = sum(max(entry.ranking_score, 0.0) for entry in entries)
    if score_sum <= 0:
        return
    for entry in entries:
        entry.allocation_weight = round(max(entry.ranking_score, 0.0) / score_sum, 4)


def _entry_row(
    snapshot_id: UUID,
    team_id: UUID,
    payload: StrategyCompetitionEntryPayload,
) -> StrategyCompetitionEntry:
    return StrategyCompetitionEntry(
        snapshot_id=snapshot_id,
        team_id=team_id,
        strategy_id=payload.strategy_id,
        name=payload.name,
        version=payload.version,
        source=payload.source,
        execution_mode=payload.execution_mode,
        status=payload.status,
        rank=payload.rank,
        ranking_score=payload.ranking_score,
        allocation_weight=payload.allocation_weight,
        eligible_for_allocation=payload.eligible_for_allocation,
        recommended_action=payload.recommended_action,
        blockers_json=json.dumps(payload.blockers),
        readiness=payload.readiness,
        promotion_gate=payload.promotion_gate,
        sample_size=payload.sample_size,
        filled_order_count=payload.filled_order_count,
        observed_pnl=payload.observed_pnl,
        primary_regime=payload.primary_regime,
        signal_quality_score=payload.signal_quality_score,
        supports_live=payload.supports_live,
        supports_hot_swap=payload.supports_hot_swap,
    )


def _snapshot_payload(
    session: Session,
    snapshot: StrategyCompetitionSnapshot,
    active_strategy_id: str,
) -> StrategyCompetitionSnapshotPayload:
    entries = [
        _entry_payload(entry)
        for entry in sorted(
            _snapshot_entries(session, snapshot),
            key=lambda item: (-item.ranking_score, item.strategy_id),
        )
    ]
    return StrategyCompetitionSnapshotPayload(
        id=snapshot.id,
        team_id=snapshot.team_id,
        trading_day=snapshot.trading_day,
        status=snapshot.status,
        active_strategy_id=active_strategy_id,
        selected_strategy_id=snapshot.selected_strategy_id,
        strategy_count=snapshot.strategy_count,
        allocatable_strategy_count=snapshot.allocatable_strategy_count,
        competition_ready=snapshot.competition_ready,
        entries=entries,
        summary=_summary(
            snapshot.strategy_count,
            snapshot.allocatable_strategy_count,
            snapshot.selected_strategy_id,
            snapshot.competition_ready,
        ),
        created_at=snapshot.created_at.isoformat(),
        updated_at=snapshot.updated_at.isoformat(),
    )


def _snapshot_entries(session: Session, snapshot: StrategyCompetitionSnapshot) -> list[StrategyCompetitionEntry]:
    return list(
        session.exec(select(StrategyCompetitionEntry).where(StrategyCompetitionEntry.snapshot_id == snapshot.id)).all()
    )


def _entry_payload(entry: StrategyCompetitionEntry) -> StrategyCompetitionEntryPayload:
    return StrategyCompetitionEntryPayload(
        strategy_id=entry.strategy_id,
        name=entry.name,
        version=entry.version,
        source=entry.source,
        execution_mode=entry.execution_mode,
        status=entry.status,
        rank=entry.rank,
        ranking_score=round(entry.ranking_score, 2),
        allocation_weight=round(entry.allocation_weight, 4),
        eligible_for_allocation=entry.eligible_for_allocation,
        recommended_action=entry.recommended_action,
        blockers=_decode_blockers(entry.blockers_json),
        readiness=entry.readiness,
        promotion_gate=entry.promotion_gate,
        sample_size=entry.sample_size,
        filled_order_count=entry.filled_order_count,
        observed_pnl=round(entry.observed_pnl, 2),
        primary_regime=entry.primary_regime,
        signal_quality_score=round(entry.signal_quality_score, 4),
        supports_live=entry.supports_live,
        supports_hot_swap=entry.supports_hot_swap,
    )


def _active_strategy_id(snapshot: StrategyCompetitionSnapshot) -> str:
    return snapshot.selected_strategy_id or "deterministic_watchlist_v1"


def _decode_blockers(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []


def _summary(strategy_count: int, allocatable_count: int, selected_strategy_id: str | None, ready: bool) -> str:
    if strategy_count == 0:
        return "Strategy competition has no registered strategies."
    if ready:
        return (
            f"Strategy competition is ready with {allocatable_count} allocatable strategies; "
            f"selected strategy: {selected_strategy_id}."
        )
    return (
        f"Strategy competition is collecting evidence: {strategy_count} strategies observed, "
        f"{allocatable_count} allocatable strategy."
    )


def _history_summary(snapshot_count: int, latest: StrategyCompetitionSnapshotPayload | None) -> str:
    if snapshot_count == 0 or latest is None:
        return "No strategy competition snapshots have been recorded yet."
    return (
        f"Strategy competition snapshots: {snapshot_count} days recorded, "
        f"latest selected strategy {latest.selected_strategy_id or 'none'}."
    )
