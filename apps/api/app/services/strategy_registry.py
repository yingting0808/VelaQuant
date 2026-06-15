import json
from dataclasses import dataclass
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.data.providers.base import MarketDataProvider
from app.domain.models import Portfolio, Position, WatchlistItem
from app.services.alpha_validation import AlphaValidationPayload, get_alpha_validation
from app.services.lean_backtest import BacktestHistoryItem, BacktestResult, read_backtest_history, read_latest_backtest
from app.services.strategy_attribution import StrategyAttributionPayload, attribute_current_paper_strategy
from app.services.strategy_catalog import StrategyDefinition, load_enabled_strategies
from app.services.strategy_evaluation import StrategyEvaluationPayload, evaluate_current_paper_strategy
from app.services.strategy_versions import DEFAULT_STRATEGY_VERSION, get_active_strategy_version
from app.trading_core.strategy import DeterministicWatchlistStrategy, MovingAverageCrossStrategy
from app.trading_core.strategy_engine import StrategyEngine


DEFAULT_PAPER_STRATEGY_ID = "deterministic_watchlist_v1"
DEFAULT_PAPER_STRATEGY_NAME = "Deterministic Watchlist Strategy"
DEFAULT_PAPER_STRATEGY_VERSION = "v1"
DEFAULT_PAPER_STRATEGY_NOTIONAL = 2000.0
MOVING_AVERAGE_CROSS_STRATEGY_ID = "moving_average_cross"
MOVING_AVERAGE_CROSS_STRATEGY_NAME = "MovingAverageCross"
REGISTERED_PAPER_RUNTIME_STRATEGY_IDS = (DEFAULT_PAPER_STRATEGY_ID, MOVING_AVERAGE_CROSS_STRATEGY_ID)
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
        backtest_history=read_backtest_history(limit=50),
        alpha_validations=[
            get_alpha_validation(session, strategy_id=strategy_id)
            for strategy_id in REGISTERED_PAPER_RUNTIME_STRATEGY_IDS
        ],
    )


def get_registered_strategy_execution_binding(
    session: Session,
    team_id: UUID,
    strategy_id: str,
    *,
    notional: float | None = None,
) -> StrategyExecutionBinding:
    normalized = _normalize_strategy_id(strategy_id)
    if normalized == DEFAULT_PAPER_STRATEGY_ID:
        return _deterministic_watchlist_binding(session, team_id, notional=notional)
    if normalized == MOVING_AVERAGE_CROSS_STRATEGY_ID:
        return _moving_average_cross_binding(session, team_id, notional=notional)
    raise ValueError(f"Strategy is not registered for execution: {normalized}")


def is_registered_execution_strategy(strategy_id: str) -> bool:
    normalized = _normalize_strategy_id(strategy_id)
    return normalized in set(REGISTERED_PAPER_RUNTIME_STRATEGY_IDS)


def _deterministic_watchlist_binding(
    session: Session,
    team_id: UUID,
    *,
    notional: float | None,
) -> StrategyExecutionBinding:
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


def _moving_average_cross_binding(
    session: Session,
    team_id: UUID,
    *,
    notional: float | None,
) -> StrategyExecutionBinding:
    universe = _execution_universe(session, team_id)
    active_version = get_active_strategy_version(session, MOVING_AVERAGE_CROSS_STRATEGY_ID)
    version_parameters = _strategy_version_parameters(active_version.parameters_json)
    version_notional = _active_strategy_notional(version_parameters)
    effective_notional = notional if notional is not None else version_notional
    if effective_notional < 0:
        raise ValueError("Strategy execution notional override must not be negative")
    strategy = MovingAverageCrossStrategy(universe=universe, notional=effective_notional)
    return StrategyExecutionBinding(
        strategy_id=MOVING_AVERAGE_CROSS_STRATEGY_ID,
        name=MOVING_AVERAGE_CROSS_STRATEGY_NAME,
        version=active_version.version or DEFAULT_STRATEGY_VERSION,
        execution_mode=StrategyExecutionMode.paper,
        strategy_engine=StrategyEngine(strategy_id=MOVING_AVERAGE_CROSS_STRATEGY_ID, strategy=strategy),
        supports_live=False,
        supports_hot_swap=True,
    )


def build_strategy_registry(
    *,
    evaluation: StrategyEvaluationPayload,
    attribution: StrategyAttributionPayload,
    catalog: list[StrategyDefinition],
    latest_backtest: BacktestResult | None,
    backtest_history: list[BacktestResult | BacktestHistoryItem] | None = None,
    alpha_validations: list[AlphaValidationPayload] | None = None,
) -> StrategyRegistryPayload:
    history = backtest_history or []
    alpha_by_strategy = {alpha.strategy_id: alpha for alpha in alpha_validations or []}
    entries = [_paper_entry(evaluation, attribution, _strategy_backtest(evaluation.strategy_id, latest_backtest, history))]
    entries.extend(
        _catalog_entry(
            strategy,
            _strategy_backtest(strategy.id, latest_backtest, history),
            alpha_by_strategy.get(strategy.id),
        )
        for strategy in catalog
        if strategy.id != evaluation.strategy_id
    )
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


def _paper_entry(
    evaluation: StrategyEvaluationPayload,
    attribution: StrategyAttributionPayload,
    backtest: BacktestResult | BacktestHistoryItem | None,
) -> StrategyRegistryEntry:
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
        backtest_status=backtest.status if backtest is not None else None,
        supports_live=False,
        supports_hot_swap=True,
        notes=evaluation.notes,
    )


def _catalog_entry(
    strategy: StrategyDefinition,
    backtest: BacktestResult | BacktestHistoryItem | None,
    alpha: AlphaValidationPayload | None = None,
) -> StrategyRegistryEntry:
    ranking_score = _catalog_ranking_score(backtest)
    has_real_backtest = backtest is not None and backtest.status == "success" and backtest.uses_real_market_data
    has_success_backtest = backtest is not None and backtest.status == "success"
    is_connected_runtime_strategy = strategy.id == MOVING_AVERAGE_CROSS_STRATEGY_ID and ranking_score > 0 and has_real_backtest
    has_runtime_alpha = (
        is_connected_runtime_strategy
        and alpha is not None
        and (alpha.review_day_count > 0 or alpha.filled_order_count > 0 or alpha.event_chain_count > 0)
    )
    return StrategyRegistryEntry(
        strategy_id=strategy.id,
        name=strategy.name,
        version="catalog",
        source="paper_core" if is_connected_runtime_strategy else "lean_catalog",
        execution_mode="paper" if is_connected_runtime_strategy else "backtest",
        status="active" if is_connected_runtime_strategy else "available",
        rank=0,
        ranking_score=ranking_score,
        readiness=(
            "paper_ready"
            if has_runtime_alpha and alpha.alpha_ready
            else "watch"
            if has_runtime_alpha
            else "backtest_promising"
            if ranking_score > 0 and has_real_backtest
            else "backtest_only"
        ),
        promotion_gate=(
            "paper_alpha_validated"
            if has_runtime_alpha and alpha.alpha_ready
            else "collect_paper_runtime_samples"
            if is_connected_runtime_strategy
            else "connect_to_paper_runtime"
            if ranking_score > 0 and has_real_backtest
            else "not_connected_to_paper_runtime"
        ),
        sample_size=alpha.review_day_count if has_runtime_alpha else 0,
        filled_order_count=alpha.filled_order_count if has_runtime_alpha else 0,
        observed_pnl=0,
        primary_regime=(
            "paper_runtime_alpha"
            if has_runtime_alpha
            else "backtest_real_market"
            if has_real_backtest
            else "backtest_research_series"
            if has_success_backtest
            else "backtest_only"
        ),
        signal_quality_score=_backtest_win_rate(backtest),
        backtest_status=backtest.status if backtest is not None else None,
        supports_live=False,
        supports_hot_swap=is_connected_runtime_strategy,
        notes=(
            f"已接入 paper runtime；已收集 {alpha.filled_order_count} 笔成交、{alpha.review_day_count} 个复盘日，继续等待 Alpha 门禁。"
            if has_runtime_alpha
            else
            "真实市场回测为正；已接入 paper runtime，需收集独立模拟盘样本，不能直接实盘。"
            if is_connected_runtime_strategy
            else "真实市场回测为正；下一步只能接入 paper runtime 继续验证，不能直接进入执行。"
            if ranking_score > 0 and has_real_backtest
            else "LEAN 目录策略可回测，但尚未接入 paper runtime 和生命周期控制。"
        ),
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


def _strategy_backtest(
    strategy_id: str,
    latest_backtest: BacktestResult | None,
    backtest_history: list[BacktestResult | BacktestHistoryItem],
) -> BacktestResult | BacktestHistoryItem | None:
    candidates: list[BacktestResult | BacktestHistoryItem] = []
    seen: set[str] = set()
    for backtest in ([latest_backtest] if latest_backtest is not None else []) + backtest_history:
        if backtest.strategy_id != strategy_id or backtest.run_id in seen:
            continue
        seen.add(backtest.run_id)
        candidates.append(backtest)
    if not candidates:
        return None
    for predicate in (
        lambda item: item.status == "success" and item.uses_real_market_data,
        lambda item: item.status == "success",
        lambda item: True,
    ):
        match = next((item for item in candidates if predicate(item)), None)
        if match is not None:
            return match
    return None


def _catalog_ranking_score(backtest: BacktestResult | BacktestHistoryItem | None) -> float:
    if backtest is None or backtest.status != "success":
        return 0.0
    net_profit = _ratio_stat(backtest.statistics.total_net_profit)
    sharpe = _float_stat(backtest.statistics.sharpe_ratio)
    drawdown = _ratio_stat(backtest.statistics.drawdown)
    total_trades = _float_stat(backtest.statistics.total_trades)
    if net_profit is None or net_profit <= 0:
        return 0.0

    net_profit_score = _clamp(net_profit / 0.2)
    sharpe_score = _clamp((sharpe or 0.0) / 2.0)
    drawdown_score = 1.0 - _clamp((drawdown or 0.0) / 0.2)
    trade_score = _clamp((total_trades or 0.0) / 30.0)
    quality_multiplier = 1.0 if backtest.uses_real_market_data else 0.5
    score = (
        net_profit_score * 0.4
        + sharpe_score * 0.3
        + drawdown_score * 0.2
        + trade_score * 0.1
    )
    return round(max(0.0, score) * quality_multiplier * 100, 2)


def _backtest_win_rate(backtest: BacktestResult | BacktestHistoryItem | None) -> float:
    if backtest is None or backtest.status != "success":
        return 0.0
    return round(_ratio_stat(backtest.statistics.win_rate) or 0.0, 4)


def _ratio_stat(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    is_percent = cleaned.endswith("%")
    if is_percent:
        cleaned = cleaned[:-1].strip()
    parsed = _float_stat(cleaned)
    if parsed is None:
        return None
    return parsed / 100 if is_percent else parsed


def _float_stat(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


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
