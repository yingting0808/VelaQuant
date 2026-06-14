from app.services.lean_backtest import BacktestResult, BacktestStatistics
from app.services.strategy_registry import get_registered_strategy_execution_binding
from app.services.strategy_attribution import (
    DrawdownAttribution,
    ExpectancyDecomposition,
    MarketRegimeAttribution,
    RegimeBreakdownPayload,
    RegimePerformanceItem,
    SignalDecayAttribution,
    SignalQualityAttribution,
    StrategyAttributionPayload,
)
from app.services.strategy_catalog import StrategyDefinition, StrategyParameterDefinition
from app.services.strategy_evaluation import StrategyEvaluationPayload, StrategyEvaluationReadiness
from app.services.strategy_registry import STRATEGY_REGISTRY_MISSING_CAPABILITIES, build_strategy_registry
from app.services.workspace import get_or_create_default_workspace
from sqlmodel import Session, SQLModel, create_engine


def test_strategy_registry_ranks_current_paper_strategy_from_alpha_evidence():
    payload = build_strategy_registry(
        evaluation=_evaluation(
            strategy_id="deterministic_watchlist_v1",
            stability_score=0.6,
            signal_precision=0.75,
            expectancy=4.2,
            max_drawdown=0.05,
            readiness=StrategyEvaluationReadiness.watch,
            promotion_gate="keep_paper_running",
        ),
        attribution=_attribution(strategy_id="deterministic_watchlist_v1", observed_pnl=125.5, primary_regime="trend_market"),
        catalog=[_catalog_strategy()],
        latest_backtest=_backtest(strategy_id="moving_average_cross", status="success"),
    )

    assert payload.active_strategy_id == "deterministic_watchlist_v1"
    assert payload.entries[0].strategy_id == "deterministic_watchlist_v1"
    assert payload.entries[0].rank == 1
    assert payload.entries[0].source == "paper_core"
    assert payload.entries[0].execution_mode == "paper"
    assert payload.entries[0].status == "active"
    assert payload.entries[0].ranking_score == 74
    assert payload.entries[0].readiness == "watch"
    assert payload.entries[0].promotion_gate == "keep_paper_running"
    assert payload.entries[0].observed_pnl == 125.5
    assert payload.entries[0].primary_regime == "trend_market"
    assert payload.entries[0].signal_quality_score == 0.5
    assert payload.entries[0].supports_live is False
    assert payload.entries[0].supports_hot_swap is True


def test_strategy_registry_marks_catalog_strategies_as_backtest_only_and_exposes_missing_controls():
    payload = build_strategy_registry(
        evaluation=_evaluation(strategy_id="deterministic_watchlist_v1"),
        attribution=_attribution(strategy_id="deterministic_watchlist_v1"),
        catalog=[_catalog_strategy()],
        latest_backtest=_backtest(strategy_id="moving_average_cross", status="failed"),
    )

    catalog_entry = next(item for item in payload.entries if item.strategy_id == "moving_average_cross")
    assert catalog_entry.rank == 2
    assert catalog_entry.source == "lean_catalog"
    assert catalog_entry.execution_mode == "backtest"
    assert catalog_entry.status == "available"
    assert catalog_entry.ranking_score == 0
    assert catalog_entry.readiness == "backtest_only"
    assert catalog_entry.backtest_status == "failed"
    assert catalog_entry.supports_live is False
    assert catalog_entry.supports_hot_swap is False
    assert catalog_entry.notes == "LEAN 目录策略可回测，但尚未接入 paper runtime 和生命周期控制。"
    assert "strategy_versioning_persistence" not in payload.missing_capabilities
    assert "hot_swap_execution_binding" not in payload.missing_capabilities
    assert "multi_strategy_parallel_runtime" not in payload.missing_capabilities
    assert "strategy_competition_runtime" not in payload.missing_capabilities
    assert payload.missing_capabilities == STRATEGY_REGISTRY_MISSING_CAPABILITIES
    assert "controls execution binding" in payload.summary
    assert "1 active paper strategy" in payload.summary
    assert "1 backtest catalog strategy" in payload.summary
    assert "manual lifecycle review" in payload.summary
    assert "no automatic promotion" in payload.summary
    assert "automation enabled" not in payload.summary


def test_strategy_registry_scores_catalog_strategy_from_real_market_backtest_history():
    payload = build_strategy_registry(
        evaluation=_evaluation(strategy_id="deterministic_watchlist_v1"),
        attribution=_attribution(strategy_id="deterministic_watchlist_v1"),
        catalog=[_catalog_strategy()],
        latest_backtest=_backtest(
            strategy_id="deterministic_watchlist_v1",
            status="success",
            uses_real_market_data=False,
            total_net_profit="2.23%",
            sharpe_ratio="0.87",
            drawdown="1.97%",
            total_trades="7",
        ),
        backtest_history=[
            _backtest(
                strategy_id="deterministic_watchlist_v1",
                status="success",
                uses_real_market_data=False,
                total_net_profit="2.23%",
                sharpe_ratio="0.87",
                drawdown="1.97%",
                total_trades="7",
            ),
            _backtest(
                strategy_id="moving_average_cross",
                status="success",
                uses_real_market_data=True,
                total_net_profit="12.34%",
                sharpe_ratio="0.72",
                drawdown="15.20%",
                win_rate="48%",
                total_trades="24",
            ),
            _backtest(
                strategy_id="moving_average_cross",
                status="failed",
                uses_real_market_data=False,
                total_net_profit=None,
                sharpe_ratio=None,
                drawdown=None,
                total_trades=None,
            ),
        ],
    )

    catalog_entry = next(item for item in payload.entries if item.strategy_id == "moving_average_cross")
    assert catalog_entry.backtest_status == "success"
    assert catalog_entry.ranking_score > 0
    assert catalog_entry.readiness == "backtest_promising"
    assert catalog_entry.promotion_gate == "connect_to_paper_runtime"
    assert catalog_entry.primary_regime == "backtest_real_market"
    assert catalog_entry.signal_quality_score == 0.48
    assert catalog_entry.notes == "真实市场回测为正；下一步只能接入 paper runtime 继续验证，不能直接进入执行。"


def test_strategy_registry_does_not_mark_negative_backtest_as_promising():
    payload = build_strategy_registry(
        evaluation=_evaluation(strategy_id="deterministic_watchlist_v1"),
        attribution=_attribution(strategy_id="deterministic_watchlist_v1"),
        catalog=[_catalog_strategy()],
        latest_backtest=_backtest(
            strategy_id="moving_average_cross",
            status="success",
            uses_real_market_data=True,
            total_net_profit="-0.02%",
            sharpe_ratio="0.06",
            drawdown="10.80%",
            win_rate="50.00%",
            total_trades="2",
        ),
    )

    catalog_entry = next(item for item in payload.entries if item.strategy_id == "moving_average_cross")
    assert catalog_entry.backtest_status == "success"
    assert catalog_entry.ranking_score == 0
    assert catalog_entry.readiness == "backtest_only"
    assert catalog_entry.promotion_gate == "not_connected_to_paper_runtime"
    assert catalog_entry.notes == "LEAN 目录策略可回测，但尚未接入 paper runtime 和生命周期控制。"


def test_strategy_registry_loads_registered_execution_binding():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        binding = get_registered_strategy_execution_binding(
            session,
            workspace.team.id,
            "deterministic_watchlist_v1",
            notional=1250,
        )

    assert binding.strategy_id == "deterministic_watchlist_v1"
    assert binding.name == "Deterministic Watchlist Strategy"
    assert binding.execution_mode == "paper"
    assert binding.strategy_engine.strategy_id == "deterministic_watchlist_v1"
    assert binding.supports_live is False
    assert binding.supports_hot_swap is True


def _evaluation(
    *,
    strategy_id: str,
    stability_score: float = 0,
    signal_precision: float = 0,
    expectancy: float = 0,
    max_drawdown: float = 0,
    readiness: StrategyEvaluationReadiness = StrategyEvaluationReadiness.insufficient_sample,
    promotion_gate: str = "blocked",
) -> StrategyEvaluationPayload:
    return StrategyEvaluationPayload(
        strategy_id=strategy_id,
        strategy_name="Deterministic Watchlist Strategy",
        sample_size=22,
        filled_order_count=21,
        rejected_order_count=1,
        closed_trade_count=5,
        signal_precision=signal_precision,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
        stability_score=stability_score,
        readiness=readiness,
        promotion_gate=promotion_gate,
        event_chain_count=80,
        notes="fixture",
    )


def _attribution(
    *,
    strategy_id: str,
    observed_pnl: float = 0,
    primary_regime: str = "insufficient_data",
) -> StrategyAttributionPayload:
    return StrategyAttributionPayload(
        strategy_id=strategy_id,
        strategy_name="Deterministic Watchlist Strategy",
        signal_quality=SignalQualityAttribution(
            market_event_count=12,
            trade_intent_count=6,
            actionable_signal_rate=0.5,
            average_confidence=0.72,
            false_positive_rate=0.25,
        ),
        ticker_diagnostics=[],
        signal_decay=SignalDecayAttribution(
            threshold_days=5,
            open_position_count=0,
            stale_open_position_count=0,
            stale_tickers=[],
            average_holding_days=0,
            basis="fixture",
        ),
        expectancy_decomposition=ExpectancyDecomposition(
            realized_pnl=100,
            unrealized_pnl=observed_pnl - 100,
            closed_trade_component=100,
            open_trade_component=observed_pnl - 100,
            total_observed_pnl=observed_pnl,
            components=[],
        ),
        regime=MarketRegimeAttribution(
            regime="uptrend_capture",
            basis="fixture",
            review_count=5,
            equity_change=0.04,
        ),
        regime_breakdown=RegimeBreakdownPayload(
            primary_regime=primary_regime,
            items=[
                RegimePerformanceItem(
                    regime="trend_market",
                    ticker_count=1 if primary_regime == "trend_market" else 0,
                    observed_pnl=observed_pnl,
                    average_return=0.08,
                    average_volatility=0.01,
                    sample_count=2,
                    sharpe_proxy=3.2,
                    tickers=["NVDA"] if primary_regime == "trend_market" else [],
                    basis="fixture",
                ),
                RegimePerformanceItem(
                    regime="range_market",
                    ticker_count=0,
                    observed_pnl=0,
                    average_return=0,
                    average_volatility=0,
                    sample_count=0,
                    sharpe_proxy=0,
                    tickers=[],
                    basis="fixture",
                ),
                RegimePerformanceItem(
                    regime="high_volatility",
                    ticker_count=0,
                    observed_pnl=0,
                    average_return=0,
                    average_volatility=0,
                    sample_count=0,
                    sharpe_proxy=0,
                    tickers=[],
                    basis="fixture",
                ),
                RegimePerformanceItem(
                    regime="insufficient_data",
                    ticker_count=0,
                    observed_pnl=0,
                    average_return=0,
                    average_volatility=0,
                    sample_count=0,
                    sharpe_proxy=0,
                    tickers=[],
                    basis="fixture",
                ),
            ],
            basis="fixture",
        ),
        drawdown=DrawdownAttribution(source="equity_curve_pressure", max_drawdown=0.05, basis="fixture"),
        data_quality_warnings=[],
        summary="fixture",
    )


def _catalog_strategy() -> StrategyDefinition:
    return StrategyDefinition(
        id="moving_average_cross",
        name="MovingAverageCross",
        description="fixture strategy",
        language="Python",
        asset_class="US Equity",
        default_symbol="AAPL",
        resolution="Daily",
        project_path="MovingAverageCross",
        enabled=True,
        parameters=[
            StrategyParameterDefinition(
                name="symbol",
                label="Ticker",
                kind="ticker",
                default="AAPL",
                required=True,
            )
        ],
    )


def _backtest(
    *,
    strategy_id: str,
    status: str,
    uses_real_market_data: bool = False,
    total_net_profit: str | None = "12.34%",
    sharpe_ratio: str | None = "0.72",
    drawdown: str | None = None,
    win_rate: str | None = None,
    total_trades: str | None = None,
) -> BacktestResult:
    return BacktestResult(
        run_id="20260612T101500Z-moving_average_cross",
        strategy_id=strategy_id,
        status=status,
        data_quality="real_market_data" if uses_real_market_data else "deterministic_research_series",
        uses_real_market_data=uses_real_market_data,
        started_at="2026-06-12T10:15:00Z",
        completed_at="2026-06-12T10:16:15Z",
        duration_seconds=75.0,
        message="Backtest completed.",
        parameters={"symbol": "AAPL"},
        statistics=BacktestStatistics(
            total_net_profit=total_net_profit,
            sharpe_ratio=sharpe_ratio,
            drawdown=drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
        ),
        equity=[],
        logs=[],
        output_directory="apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross",
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
