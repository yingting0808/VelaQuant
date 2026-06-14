from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from app.services.strategy_evaluation import evaluate_current_paper_strategy
from app.services.strategy_lifecycle import StrategyLifecyclePayload, get_strategy_lifecycle
from app.services.strategy_versions import get_strategy_version_control


class StrategyRuntimeCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    ranking_score: float
    eligible: bool
    block_reason: str | None = None


class StrategyRuntimeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    version: str
    ranking_score: float
    eligible: bool
    rank: int
    block_reason: str | None = None


class StrategyCompetitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    winner: StrategyRuntimeEntry | None
    entries: list[StrategyRuntimeEntry]
    summary: str


def run_strategy_competition(strategies: list[StrategyRuntimeCandidate]) -> StrategyCompetitionResult:
    entries = [
        StrategyRuntimeEntry(
            strategy_id=strategy.strategy_id,
            version=strategy.version,
            ranking_score=strategy.ranking_score,
            eligible=strategy.eligible,
            rank=0,
            block_reason=strategy.block_reason,
        )
        for strategy in strategies
    ]
    ranked_entries = [
        entry.model_copy(update={"rank": index + 1})
        for index, entry in enumerate(
            sorted(
                entries,
                key=lambda item: (
                    0 if item.eligible else 1,
                    -item.ranking_score,
                    item.strategy_id,
                    item.version,
                ),
            )
        )
    ]
    winner = next((entry for entry in ranked_entries if entry.eligible), None)
    return StrategyCompetitionResult(
        winner=winner,
        entries=ranked_entries,
        summary=_summary(winner, ranked_entries),
    )


def get_strategy_runtime_status(session: Session) -> StrategyCompetitionResult:
    evaluation = evaluate_current_paper_strategy(session)
    lifecycle = get_strategy_lifecycle(session)
    version_control = get_strategy_version_control(session, evaluation.strategy_id)
    base_score = _ranking_score_from_evaluation(evaluation.stability_score, evaluation.signal_precision, evaluation.expectancy)
    lifecycle_block_reason = _lifecycle_runtime_block_reason(lifecycle)
    candidates = [
        StrategyRuntimeCandidate(
            strategy_id=version.strategy_id,
            version=version.version,
            ranking_score=base_score + (1.0 if version.is_active else 0.0),
            eligible=lifecycle_block_reason is None,
            block_reason=lifecycle_block_reason,
        )
        for version in version_control.versions
    ]
    return run_strategy_competition(candidates)


def _summary(winner: StrategyRuntimeEntry | None, entries: list[StrategyRuntimeEntry]) -> str:
    eligible_count = len([entry for entry in entries if entry.eligible])
    if winner is None:
        return f"No eligible strategy runtime candidates across {len(entries)} registered candidates."
    return (
        f"Selected {winner.strategy_id}@{winner.version} from "
        f"{eligible_count} eligible runtime candidates."
    )


def _ranking_score_from_evaluation(stability_score: float, signal_precision: float, expectancy: float) -> float:
    expectancy_score = 10.0 if expectancy > 0 else 0.0
    return round(stability_score * 60 + signal_precision * 30 + expectancy_score, 2)


def _lifecycle_runtime_block_reason(lifecycle: StrategyLifecyclePayload) -> str | None:
    if lifecycle.current_stage == "killed":
        return "strategy_killed"
    if lifecycle.can_kill or lifecycle.recommended_stage == "killed":
        return "strategy_kill_review_required"
    return None
