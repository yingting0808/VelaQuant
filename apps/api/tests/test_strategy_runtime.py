import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services import strategy_runtime
from app.services.strategy_evaluation import StrategyEvaluationPayload, StrategyEvaluationReadiness
from app.services.strategy_lifecycle import StrategyLifecyclePayload
from app.services.strategy_runtime import StrategyRuntimeCandidate, get_strategy_runtime_status, run_strategy_competition
from app.services.strategy_versions import StrategyVersionControlPayload, StrategyVersionPayload


def test_strategy_runtime_scores_multiple_registered_strategies():
    result = run_strategy_competition(
        strategies=[
            StrategyRuntimeCandidate(
                strategy_id="deterministic_watchlist_v1",
                version="v1",
                ranking_score=60,
                eligible=True,
            ),
            StrategyRuntimeCandidate(
                strategy_id="deterministic_watchlist_v1",
                version="v2",
                ranking_score=72,
                eligible=True,
            ),
        ]
    )

    assert result.winner is not None
    assert result.winner.strategy_id == "deterministic_watchlist_v1"
    assert result.winner.version == "v2"
    assert [entry.rank for entry in result.entries] == [1, 2]
    assert [entry.version for entry in result.entries] == ["v2", "v1"]


def test_strategy_runtime_does_not_select_blocked_high_score_candidate():
    result = run_strategy_competition(
        strategies=[
            StrategyRuntimeCandidate(
                strategy_id="deterministic_watchlist_v1",
                version="v1",
                ranking_score=60,
                eligible=True,
            ),
            StrategyRuntimeCandidate(
                strategy_id="experimental_watchlist_v1",
                version="v1",
                ranking_score=99,
                eligible=False,
                block_reason="lifecycle blocked",
            ),
        ]
    )

    assert result.winner is not None
    assert result.winner.strategy_id == "deterministic_watchlist_v1"
    assert result.entries[0].strategy_id == "deterministic_watchlist_v1"
    assert result.entries[1].strategy_id == "experimental_watchlist_v1"
    assert result.entries[1].block_reason == "lifecycle blocked"


@pytest.mark.parametrize(
    ("lifecycle_payload", "block_reason"),
    [
        (
            StrategyLifecyclePayload(
                strategy_id="deterministic_watchlist_v1",
                strategy_name="Deterministic Watchlist Strategy",
                current_stage="killed",
                recommended_stage="killed",
                recommended_action="hold_current_stage",
                gate_status="blocked",
                promotion_gate="strategy_killed",
                can_promote=False,
                can_kill=False,
                auto_actions_enabled=False,
                rules=[],
                missing_capabilities=[],
                summary="Strategy is killed.",
            ),
            "strategy_killed",
        ),
        (
            StrategyLifecyclePayload(
                strategy_id="deterministic_watchlist_v1",
                strategy_name="Deterministic Watchlist Strategy",
                current_stage="shadow",
                recommended_stage="killed",
                recommended_action="kill_review",
                gate_status="blocked",
                promotion_gate="negative_expectancy",
                can_promote=False,
                can_kill=True,
                auto_actions_enabled=False,
                rules=[],
                missing_capabilities=[],
                summary="Strategy requires kill review.",
            ),
            "strategy_kill_review_required",
        ),
    ],
)
def test_strategy_runtime_blocks_candidates_when_lifecycle_is_killed_or_under_kill_review(
    monkeypatch,
    lifecycle_payload,
    block_reason,
):
    with make_session() as session:
        monkeypatch.setattr(strategy_runtime, "evaluate_current_paper_strategy", lambda session: evaluation())
        monkeypatch.setattr(strategy_runtime, "get_strategy_version_control", lambda session, strategy_id: versions())
        monkeypatch.setattr(strategy_runtime, "get_strategy_lifecycle", lambda session: lifecycle_payload)

        result = get_strategy_runtime_status(session)

    assert result.winner is None
    assert result.entries[0].eligible is False
    assert result.entries[0].block_reason == block_reason


def evaluation() -> StrategyEvaluationPayload:
    return StrategyEvaluationPayload(
        strategy_id="deterministic_watchlist_v1",
        strategy_name="Deterministic Watchlist Strategy",
        sample_size=30,
        filled_order_count=20,
        rejected_order_count=0,
        closed_trade_count=10,
        signal_precision=0.8,
        expectancy=12,
        max_drawdown=0.04,
        stability_score=0.9,
        readiness=StrategyEvaluationReadiness.paper_ready,
        promotion_gate="eligible_for_shadow",
        event_chain_count=20,
        notes="ready",
    )


def versions() -> StrategyVersionControlPayload:
    return StrategyVersionControlPayload(
        active_strategy_id="deterministic_watchlist_v1",
        active_version="v1",
        previous_version=None,
        versions=[
            StrategyVersionPayload(
                strategy_id="deterministic_watchlist_v1",
                version="v1",
                parameters_json="{}",
                status="registered",
                is_active=True,
            )
        ],
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
