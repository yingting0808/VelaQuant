from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.data.providers.base import MarketDataProvider
from app.services.lean_backtest import BacktestResult, read_latest_backtest
from app.services.strategy_attribution import StrategyAttributionPayload, attribute_current_paper_strategy
from app.services.strategy_catalog import StrategyDefinition, load_enabled_strategies
from app.services.strategy_evaluation import StrategyEvaluationPayload, evaluate_current_paper_strategy


STRATEGY_REGISTRY_MISSING_CAPABILITIES = [
    "strategy_versioning_persistence",
    "multi_strategy_parallel_runtime",
    "strategy_competition_runtime",
    "hot_swap_execution_binding",
    "automatic_lifecycle_actions",
]


class StrategyRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    name: str
    version: str
    source: Literal["paper_core", "lean_catalog"]
    execution_mode: Literal["paper", "backtest"]
    status: Literal["active", "available", "blocked"]
    rank: int
    ranking_score: float
    readiness: str
    promotion_gate: str
    sample_size: int
    filled_order_count: int
    observed_pnl: float
    primary_regime: str
    signal_quality_score: float
    backtest_status: str | None
    supports_live: bool
    supports_hot_swap: bool
    notes: str


class StrategyRegistryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_strategy_id: str
    entries: list[StrategyRegistryEntry]
    missing_capabilities: list[str]
    summary: str


def get_strategy_registry(
    session: Session,
    provider: MarketDataProvider | None = None,
) -> StrategyRegistryPayload:
    evaluation = evaluate_current_paper_strategy(session)
    attribution = attribute_current_paper_strategy(session, provider=provider)
    return build_strategy_registry(
        evaluation=evaluation,
        attribution=attribution,
        catalog=load_enabled_strategies(),
        latest_backtest=read_latest_backtest(),
    )


def build_strategy_registry(
    *,
    evaluation: StrategyEvaluationPayload,
    attribution: StrategyAttributionPayload,
    catalog: list[StrategyDefinition],
    latest_backtest: BacktestResult | None,
) -> StrategyRegistryPayload:
    entries = [_paper_entry(evaluation, attribution)]
    entries.extend(_catalog_entry(strategy, latest_backtest) for strategy in catalog if strategy.id != evaluation.strategy_id)
    ranked_entries = _rank(entries)
    backtest_catalog_count = len([entry for entry in ranked_entries if entry.source == "lean_catalog"])
    catalog_noun = "strategy" if backtest_catalog_count == 1 else "strategies"
    return StrategyRegistryPayload(
        active_strategy_id=evaluation.strategy_id,
        entries=ranked_entries,
        missing_capabilities=STRATEGY_REGISTRY_MISSING_CAPABILITIES.copy(),
        summary=(
            "Registry is read-only: "
            "1 active paper strategy, "
            f"{backtest_catalog_count} backtest catalog {catalog_noun}, "
            "no lifecycle automation."
        ),
    )


def _paper_entry(evaluation: StrategyEvaluationPayload, attribution: StrategyAttributionPayload) -> StrategyRegistryEntry:
    return StrategyRegistryEntry(
        strategy_id=evaluation.strategy_id,
        name=evaluation.strategy_name,
        version="v1",
        source="paper_core",
        execution_mode="paper",
        status="active",
        rank=0,
        ranking_score=_paper_ranking_score(evaluation),
        readiness=evaluation.readiness.value,
        promotion_gate=evaluation.promotion_gate,
        sample_size=evaluation.sample_size,
        filled_order_count=evaluation.filled_order_count,
        observed_pnl=round(attribution.expectancy_decomposition.total_observed_pnl, 2),
        primary_regime=attribution.regime_breakdown.primary_regime,
        signal_quality_score=attribution.signal_quality.actionable_signal_rate,
        backtest_status=None,
        supports_live=False,
        supports_hot_swap=False,
        notes=evaluation.notes,
    )


def _catalog_entry(strategy: StrategyDefinition, latest_backtest: BacktestResult | None) -> StrategyRegistryEntry:
    backtest_status = latest_backtest.status if latest_backtest is not None and latest_backtest.strategy_id == strategy.id else None
    return StrategyRegistryEntry(
        strategy_id=strategy.id,
        name=strategy.name,
        version="catalog",
        source="lean_catalog",
        execution_mode="backtest",
        status="available",
        rank=0,
        ranking_score=0,
        readiness="backtest_only",
        promotion_gate="not_connected_to_paper_runtime",
        sample_size=0,
        filled_order_count=0,
        observed_pnl=0,
        primary_regime="backtest_only",
        signal_quality_score=0,
        backtest_status=backtest_status,
        supports_live=False,
        supports_hot_swap=False,
        notes="LEAN 目录策略可回测，但尚未接入 paper runtime 和生命周期控制。",
    )


def _paper_ranking_score(evaluation: StrategyEvaluationPayload) -> float:
    expectancy_score = 1.0 if evaluation.expectancy > 0 else 0.0
    drawdown_score = max(0.0, 1 - min(evaluation.max_drawdown / 0.2, 1.0))
    score = (
        evaluation.stability_score * 0.4
        + evaluation.signal_precision * 0.2
        + expectancy_score * 0.2
        + drawdown_score * 0.2
    )
    return round(score * 100, 2)


def _rank(entries: list[StrategyRegistryEntry]) -> list[StrategyRegistryEntry]:
    source_order = {"paper_core": 0, "lean_catalog": 1}
    sorted_entries = sorted(entries, key=lambda item: (-item.ranking_score, source_order[item.source], item.strategy_id))
    return [entry.model_copy(update={"rank": index + 1}) for index, entry in enumerate(sorted_entries)]
