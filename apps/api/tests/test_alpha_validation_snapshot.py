from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import StrategyAlphaSnapshot
from app.services.alpha_validation import AlphaValidationPayload
from app.services.alpha_validation_snapshot import (
    get_alpha_validation_snapshots,
    record_alpha_validation_snapshot_from_payload,
)
from app.services.workspace import get_or_create_default_workspace


def test_alpha_validation_snapshot_records_runtime_facts_once_per_trading_day():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        alpha = alpha_payload(latest_expectancy=42.5, blockers=["closed_trade_sample"])

        first = record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-14",
            alpha=alpha,
        )
        second = record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-14",
            alpha=alpha.model_copy(update={"latest_expectancy": 55.0, "blockers": []}),
        )

        rows = session.exec(select(StrategyAlphaSnapshot)).all()
        assert len(rows) == 1
        assert second.id == first.id
        assert second.latest_expectancy == 55.0
        assert second.blockers == []
        assert second.alpha_ready is False
        assert second.validation_level == "collecting"


def test_alpha_validation_snapshot_history_returns_latest_first_and_progress_counts():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-13",
            alpha=alpha_payload(latest_expectancy=15, blockers=["filled_order_sample"]),
        )
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-14",
            alpha=alpha_payload(latest_expectancy=35, blockers=[]),
        )

        history = get_alpha_validation_snapshots(session, team_id=workspace.team.id, as_of_trading_day="2026-06-14")

        assert history.snapshot_count == 2
        assert history.positive_expectancy_snapshot_count == 2
        assert history.ready_snapshot_count == 1
        assert history.latest is not None
        assert history.latest.trading_day == "2026-06-14"
        assert [item.trading_day for item in history.items] == ["2026-06-14", "2026-06-13"]


def test_alpha_validation_snapshot_history_summarizes_streaks_and_blockers():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-12",
            alpha=alpha_payload(latest_expectancy=-10, blockers=["latest_positive_expectancy"]),
        )
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-13",
            alpha=alpha_payload(latest_expectancy=15, blockers=["closed_trade_sample", "filled_order_sample"]),
        )
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-14",
            alpha=alpha_payload(latest_expectancy=35, blockers=["closed_trade_sample"]),
        )

        history = get_alpha_validation_snapshots(session, team_id=workspace.team.id, as_of_trading_day="2026-06-14")

        assert history.positive_expectancy_streak == 2
        assert history.ready_streak == 0
        assert history.latest_blockers == ["closed_trade_sample"]
        assert [(item.blocker, item.count) for item in history.blocker_counts] == [
            ("closed_trade_sample", 2),
            ("filled_order_sample", 1),
            ("latest_positive_expectancy", 1),
        ]


def test_alpha_validation_snapshot_history_excludes_future_snapshots_by_default_window():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-12",
            alpha=alpha_payload(latest_expectancy=35, blockers=["closed_trade_sample"]),
        )
        record_alpha_validation_snapshot_from_payload(
            session,
            team_id=workspace.team.id,
            trading_day="2026-08-01",
            alpha=alpha_payload(latest_expectancy=102, blockers=[]),
        )

        history = get_alpha_validation_snapshots(session, team_id=workspace.team.id, as_of_trading_day="2026-06-12")

        assert history.snapshot_count == 1
        assert history.latest is not None
        assert history.latest.trading_day == "2026-06-12"
        assert [item.trading_day for item in history.items] == ["2026-06-12"]


def alpha_payload(*, latest_expectancy: float, blockers: list[str]) -> AlphaValidationPayload:
    return AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=not blockers,
        validation_level="paper_validated" if not blockers else "collecting",
        blockers=blockers,
        has_real_market_backtest="real_market_backtest" not in blockers,
        review_day_count=5,
        consecutive_positive_expectancy_days=4,
        filled_order_count=20,
        closed_trade_count=6,
        event_chain_count=3,
        latest_expectancy=latest_expectancy,
        average_expectancy=25.0,
        max_drawdown=0.03,
        summary="alpha facts",
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
