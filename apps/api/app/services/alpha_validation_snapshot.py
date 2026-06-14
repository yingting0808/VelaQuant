import json
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import StrategyAlphaSnapshot, utc_now
from app.services.alpha_validation import AlphaValidationPayload, get_alpha_validation
from app.services.market_calendar import current_market_trading_day
from app.services.workspace import get_or_create_default_workspace


class AlphaValidationSnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    team_id: UUID
    strategy_id: str
    trading_day: str
    alpha_ready: bool
    validation_level: str
    blockers: list[str]
    review_day_count: int
    consecutive_positive_expectancy_days: int
    filled_order_count: int
    closed_trade_count: int
    event_chain_count: int
    latest_expectancy: float
    average_expectancy: float
    max_drawdown: float
    created_at: str
    updated_at: str


class AlphaValidationSnapshotBlockerCountPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocker: str
    count: int


class AlphaValidationSnapshotHistoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    snapshot_count: int
    ready_snapshot_count: int
    positive_expectancy_snapshot_count: int
    positive_expectancy_streak: int
    ready_streak: int
    latest_blockers: list[str]
    blocker_counts: list[AlphaValidationSnapshotBlockerCountPayload]
    latest: AlphaValidationSnapshotPayload | None
    items: list[AlphaValidationSnapshotPayload]
    summary: str


def record_alpha_validation_snapshot(
    session: Session,
    *,
    team_id: UUID | None = None,
    strategy_id: str = "deterministic_watchlist_v1",
    trading_day: str | None = None,
) -> AlphaValidationSnapshotPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    trading_day = trading_day or current_market_trading_day()
    alpha = get_alpha_validation(session, team_id=team_id, strategy_id=strategy_id, as_of_trading_day=trading_day)
    return record_alpha_validation_snapshot_from_payload(
        session,
        team_id=team_id,
        trading_day=trading_day,
        alpha=alpha,
    )


def record_alpha_validation_snapshot_from_payload(
    session: Session,
    *,
    team_id: UUID,
    trading_day: str,
    alpha: AlphaValidationPayload,
) -> AlphaValidationSnapshotPayload:
    snapshot = session.exec(
        select(StrategyAlphaSnapshot).where(
            StrategyAlphaSnapshot.team_id == team_id,
            StrategyAlphaSnapshot.strategy_id == alpha.strategy_id,
            StrategyAlphaSnapshot.trading_day == trading_day,
        )
    ).first()
    if snapshot is None:
        snapshot = StrategyAlphaSnapshot(
            team_id=team_id,
            strategy_id=alpha.strategy_id,
            trading_day=trading_day,
        )
    _apply_alpha(snapshot, alpha)
    snapshot.updated_at = utc_now()
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return _payload(snapshot)


def get_alpha_validation_snapshots(
    session: Session,
    *,
    team_id: UUID | None = None,
    strategy_id: str = "deterministic_watchlist_v1",
    as_of_trading_day: str | None = None,
    limit: int = 20,
) -> AlphaValidationSnapshotHistoryPayload:
    if team_id is None:
        team_id = get_or_create_default_workspace(session).team.id
    as_of_trading_day = as_of_trading_day or current_market_trading_day()
    rows = list(
        session.exec(
            select(StrategyAlphaSnapshot)
            .where(StrategyAlphaSnapshot.team_id == team_id, StrategyAlphaSnapshot.strategy_id == strategy_id)
            .where(StrategyAlphaSnapshot.trading_day <= as_of_trading_day)
            .order_by(StrategyAlphaSnapshot.trading_day.desc(), StrategyAlphaSnapshot.updated_at.desc())
        ).all()
    )
    items = [_payload(row) for row in rows[:limit]]
    latest = items[0] if items else None
    ready_count = sum(1 for row in rows if row.alpha_ready)
    positive_count = sum(1 for row in rows if row.latest_expectancy > 0 and row.average_expectancy > 0)
    latest_blockers = _blockers(rows[0].blockers_json) if rows else []
    return AlphaValidationSnapshotHistoryPayload(
        strategy_id=strategy_id,
        snapshot_count=len(rows),
        ready_snapshot_count=ready_count,
        positive_expectancy_snapshot_count=positive_count,
        positive_expectancy_streak=_streak(rows, lambda row: row.latest_expectancy > 0 and row.average_expectancy > 0),
        ready_streak=_streak(rows, lambda row: row.alpha_ready),
        latest_blockers=latest_blockers,
        blocker_counts=_blocker_counts(rows),
        latest=latest,
        items=items,
        summary=_summary(len(rows), ready_count, positive_count),
    )


def _apply_alpha(snapshot: StrategyAlphaSnapshot, alpha: AlphaValidationPayload) -> None:
    snapshot.alpha_ready = alpha.alpha_ready
    snapshot.validation_level = alpha.validation_level
    snapshot.blockers_json = json.dumps(alpha.blockers)
    snapshot.review_day_count = alpha.review_day_count
    snapshot.consecutive_positive_expectancy_days = alpha.consecutive_positive_expectancy_days
    snapshot.filled_order_count = alpha.filled_order_count
    snapshot.closed_trade_count = alpha.closed_trade_count
    snapshot.event_chain_count = alpha.event_chain_count
    snapshot.latest_expectancy = alpha.latest_expectancy
    snapshot.average_expectancy = alpha.average_expectancy
    snapshot.max_drawdown = alpha.max_drawdown


def _payload(snapshot: StrategyAlphaSnapshot) -> AlphaValidationSnapshotPayload:
    return AlphaValidationSnapshotPayload(
        id=snapshot.id,
        team_id=snapshot.team_id,
        strategy_id=snapshot.strategy_id,
        trading_day=snapshot.trading_day,
        alpha_ready=snapshot.alpha_ready,
        validation_level=snapshot.validation_level,
        blockers=_blockers(snapshot.blockers_json),
        review_day_count=snapshot.review_day_count,
        consecutive_positive_expectancy_days=snapshot.consecutive_positive_expectancy_days,
        filled_order_count=snapshot.filled_order_count,
        closed_trade_count=snapshot.closed_trade_count,
        event_chain_count=snapshot.event_chain_count,
        latest_expectancy=round(snapshot.latest_expectancy, 2),
        average_expectancy=round(snapshot.average_expectancy, 2),
        max_drawdown=round(snapshot.max_drawdown, 4),
        created_at=snapshot.created_at.isoformat(),
        updated_at=snapshot.updated_at.isoformat(),
    )


def _blockers(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []


def _streak(rows: list[StrategyAlphaSnapshot], predicate: Callable[[StrategyAlphaSnapshot], bool]) -> int:
    count = 0
    for row in rows:
        if not predicate(row):
            break
        count += 1
    return count


def _blocker_counts(rows: list[StrategyAlphaSnapshot]) -> list[AlphaValidationSnapshotBlockerCountPayload]:
    counts: dict[str, int] = {}
    for row in rows:
        for blocker in _blockers(row.blockers_json):
            counts[blocker] = counts.get(blocker, 0) + 1
    return [
        AlphaValidationSnapshotBlockerCountPayload(blocker=blocker, count=count)
        for blocker, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _summary(snapshot_count: int, ready_count: int, positive_count: int) -> str:
    if snapshot_count == 0:
        return "No alpha validation snapshots have been recorded yet."
    return (
        f"Alpha validation snapshots: {snapshot_count} days recorded, "
        f"{positive_count} positive-expectancy days, {ready_count} ready days."
    )
