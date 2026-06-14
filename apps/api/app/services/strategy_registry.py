import json
from dataclasses import dataclass
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.data.providers.base import MarketDataProvider
from app.domain.models import Portfolio, Position, WatchlistItem
from app.services.lean_backtest import BacktestResult, read_latest_backtest
from app.services.strategy_attribution import StrategyAttributionPayload, attribute_current_paper_strategy
from app.services.strategy_catalog import StrategyDefinition, load_enabled_strategies
from app.services.strategy_evaluation import StrategyEvaluationPayload, evaluate_current_paper_strategy
from app.services.strategy_versions import DEFAULT_STRATEGY_VERSION, get_active_strategy_version
from app.trading_core.strategy import DeterministicWatchlistStrategy
from app.trading_core.strategy_engine import StrategyEngine


DEFAULT_PAPER_STRATEGY_ID = "deterministic_watchlist_v1"
DEFAULT_PAPER_STRATEGY_NAME = "Deterministic Watchlist Strategy"
DEFAULT_PAPER_STRATEGY_VERSION = "v1"
DEFAULT_PAPER_STRATEGY_NOTIONAL = 2000.0
STRATEGY_REGISTRY_MISSING_CAPABILITIES = [
]


class StrategyExecutionMode(str, Enum):
    paper = "paper"
    shadow = "shadow"
    live_small = "live_small"
    live = "live"


@dataclass(frozen=True)
class StrategyExecutionBinding:
    strategy_id: str
    name: str
    version: str
    execution_mode: StrategyExecutionMode
    strategy_engine: StrategyEngine
    supports_live: bool
    supports_hot_swap: bool


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


def get_registered_strategy_execution_binding(
    session: Session,
    team_id: UUID,
    strategy_id: str,
    *,
    notional: float | None = None,
) -> StrategyExecutionBinding:
    normalized = _normalize_strategy_id(strategy_id)
    if normalized != DEFAULT_PAPER_STRATEGY_ID:
        raise ValueError(f"Strategy is not registered for execution: {normalized}")

    watchlist = _execution_universe(session, team_id)
    active_version = get_active_strategy_version(session, DEFAULT_PAPER_STRATEGY_ID)
    version_parameters = _strategy_version_parameters(active_version.parameters_json)
    version_notional = _active_strategy_notional(version_parameters)
    effective_notional = notional if notional is not None else version_notional
    if effective_notional < 0:
        raise ValueError("Strategy execution notional override must not be negative")
    strategy = DeterministicWatchlistStrategy(watchlist=watchlist, notional=effective_notional)
    return StrategyExecutionBinding(
        strategy_id=DEFAULT_PAPER_STRATEGY_ID,
        name=DEFAULT_PAPER_STRATEGY_NAME,
        version=active_version.version or DEFAULT_STRATEGY_VERSION,
        execution_mode=StrategyExecutionMode.paper,
        strategy_engine=StrategyEngine(strategy_id=DEFAULT_PAPER_STRATEGY_ID, strategy=strategy),
        supports_live=False,
        supports_hot_swap=True,
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
            "Registry controls execution binding: "
            "1 active paper strategy, "
            f"{backtest_catalog_count} backtest catalog {catalog_noun}, "
            "manual lifecycle review required with no automatic promotion."
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
        supports_hot_swap=True,
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


def _execution_universe(session: Session, team_id: UUID) -> list[str]:
    tickers = {
        item.ticker
        for item in session.exec(select(WatchlistItem).where(WatchlistItem.team_id == team_id)).all()
    }
    portfolios = session.exec(select(Portfolio).where(Portfolio.team_id == team_id)).all()
    for portfolio in portfolios:
        tickers.update(
            position.ticker
            for position in session.exec(select(Position).where(Position.portfolio_id == portfolio.id)).all()
        )
    return sorted(ticker for ticker in tickers if ticker)


def _normalize_strategy_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("strategy_id must not be empty")
    return normalized


def _strategy_version_parameters(parameters_json: str) -> dict[str, float | int | str | bool | None]:
    try:
        parsed = json.loads(parameters_json)
    except json.JSONDecodeError as error:
        raise ValueError("Active strategy version parameters_json is invalid") from error
    if not isinstance(parsed, dict):
        raise ValueError("Active strategy version parameters_json must encode an object")
    return parsed


def _active_strategy_notional(parameters: dict[str, float | int | str | bool | None]) -> float:
    raw_notional = parameters.get("notional", DEFAULT_PAPER_STRATEGY_NOTIONAL)
    if not isinstance(raw_notional, int | float) or isinstance(raw_notional, bool):
        raise ValueError("Active strategy notional must be numeric")
    notional = float(raw_notional)
    if notional <= 0:
        raise ValueError("Active strategy notional must be positive")
    return notional
