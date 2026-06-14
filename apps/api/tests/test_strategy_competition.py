from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import StrategyCompetitionEntry, StrategyCompetitionSnapshot
from app.services.strategy_competition import (
    build_strategy_competition,
    get_strategy_competition_snapshots,
    record_strategy_competition_snapshot_from_payload,
)
from app.services.strategy_registry import StrategyRegistryEntry, StrategyRegistryPayload
from app.services.workspace import get_or_create_default_workspace


def test_strategy_competition_allocates_only_executable_paper_strategies():
    payload = build_strategy_competition(
        registry=registry_payload(
            [
                registry_entry(
                    strategy_id="deterministic_watchlist_v1",
                    source="paper_core",
                    execution_mode="paper",
                    status="active",
                    ranking_score=80,
                    readiness="paper_ready",
                    filled_order_count=40,
                    supports_hot_swap=True,
                ),
                registry_entry(
                    strategy_id="mean_reversion_shadow_v1",
                    source="paper_core",
                    execution_mode="paper",
                    status="active",
                    ranking_score=20,
                    readiness="watch",
                    filled_order_count=32,
                    supports_hot_swap=True,
                ),
                registry_entry(
                    strategy_id="moving_average_cross",
                    source="lean_catalog",
                    execution_mode="backtest",
                    status="available",
                    ranking_score=65,
                    readiness="backtest_only",
                    filled_order_count=0,
                    supports_hot_swap=False,
                ),
            ]
        ),
        trading_day="2026-06-14",
    )

    assert payload.strategy_count == 3
    assert payload.allocatable_strategy_count == 2
    assert payload.competition_ready is True
    assert payload.selected_strategy_id == "deterministic_watchlist_v1"
    assert payload.status == "allocation_ready"
    assert [(item.strategy_id, item.allocation_weight, item.recommended_action) for item in payload.entries] == [
        ("deterministic_watchlist_v1", 0.8, "allocate_paper_capital"),
        ("moving_average_cross", 0.0, "keep_in_lab"),
        ("mean_reversion_shadow_v1", 0.2, "allocate_paper_capital"),
    ]
    catalog_entry = next(item for item in payload.entries if item.strategy_id == "moving_average_cross")
    assert catalog_entry.eligible_for_allocation is False
    assert "not_connected_to_paper_runtime" in catalog_entry.blockers


def test_strategy_competition_marks_promising_backtests_for_paper_runtime_connection():
    payload = build_strategy_competition(
        registry=registry_payload(
            [
                registry_entry(
                    strategy_id="deterministic_watchlist_v1",
                    source="paper_core",
                    execution_mode="paper",
                    status="active",
                    ranking_score=80,
                    readiness="paper_ready",
                    filled_order_count=40,
                    supports_hot_swap=True,
                ),
                registry_entry(
                    strategy_id="moving_average_cross",
                    source="lean_catalog",
                    execution_mode="backtest",
                    status="available",
                    ranking_score=55,
                    readiness="backtest_promising",
                    filled_order_count=0,
                    supports_hot_swap=False,
                ),
            ]
        ),
        trading_day="2026-06-14",
    )

    catalog_entry = next(item for item in payload.entries if item.strategy_id == "moving_average_cross")
    assert catalog_entry.eligible_for_allocation is False
    assert catalog_entry.allocation_weight == 0
    assert catalog_entry.recommended_action == "connect_to_paper_runtime"
    assert "not_connected_to_paper_runtime" in catalog_entry.blockers
    assert "hot_swap_not_supported" in catalog_entry.blockers
    assert payload.selected_strategy_id == "deterministic_watchlist_v1"


def test_strategy_competition_snapshot_persists_entries_once_per_day():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        payload = build_strategy_competition(
            registry=registry_payload(
                [
                    registry_entry(
                        strategy_id="deterministic_watchlist_v1",
                        source="paper_core",
                        execution_mode="paper",
                        status="active",
                        ranking_score=70,
                        readiness="watch",
                        filled_order_count=35,
                        supports_hot_swap=True,
                    ),
                    registry_entry(
                        strategy_id="moving_average_cross",
                        source="lean_catalog",
                        execution_mode="backtest",
                        status="available",
                        ranking_score=0,
                        readiness="backtest_only",
                        filled_order_count=0,
                        supports_hot_swap=False,
                    ),
                ]
            ),
            trading_day="2026-06-14",
        )

        first = record_strategy_competition_snapshot_from_payload(session, team_id=workspace.team.id, payload=payload)
        second = record_strategy_competition_snapshot_from_payload(session, team_id=workspace.team.id, payload=payload)
        history = get_strategy_competition_snapshots(session, team_id=workspace.team.id)

        snapshots = session.exec(select(StrategyCompetitionSnapshot)).all()
        entries = session.exec(select(StrategyCompetitionEntry)).all()
        assert len(snapshots) == 1
        assert len(entries) == 2
        assert second.id == first.id
        assert history.snapshot_count == 1
        assert history.latest is not None
        assert history.latest.selected_strategy_id == "deterministic_watchlist_v1"
        assert [item.strategy_id for item in history.latest.entries] == [
            "deterministic_watchlist_v1",
            "moving_average_cross",
        ]


def registry_payload(entries: list[StrategyRegistryEntry]) -> StrategyRegistryPayload:
    return StrategyRegistryPayload(
        active_strategy_id="deterministic_watchlist_v1",
        entries=entries,
        missing_capabilities=[],
        summary="fixture registry",
    )


def registry_entry(
    *,
    strategy_id: str,
    source: str,
    execution_mode: str,
    status: str,
    ranking_score: float,
    readiness: str,
    filled_order_count: int,
    supports_hot_swap: bool,
) -> StrategyRegistryEntry:
    return StrategyRegistryEntry(
        strategy_id=strategy_id,
        name=strategy_id,
        version="v1",
        source=source,
        execution_mode=execution_mode,
        status=status,
        rank=0,
        ranking_score=ranking_score,
        readiness=readiness,
        promotion_gate="eligible_for_shadow" if readiness == "paper_ready" else "keep_paper_running",
        sample_size=filled_order_count + 2,
        filled_order_count=filled_order_count,
        observed_pnl=ranking_score * 10,
        primary_regime="range_market",
        signal_quality_score=0.7,
        backtest_status=None,
        supports_live=False,
        supports_hot_swap=supports_hot_swap,
        notes="fixture",
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
