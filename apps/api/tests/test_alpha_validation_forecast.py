from app.services.alpha_validation import AlphaValidationPayload
from app.services.alpha_validation_forecast import build_alpha_validation_forecast


def test_alpha_validation_forecast_estimates_sessions_from_current_rates():
    alpha = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=False,
        validation_level="collecting",
        blockers=["consecutive_positive_expectancy", "filled_order_sample", "closed_trade_sample"],
        review_day_count=10,
        consecutive_positive_expectancy_days=4,
        filled_order_count=20,
        closed_trade_count=9,
        event_chain_count=120,
        has_real_market_backtest=True,
        latest_expectancy=102.91,
        average_expectancy=57.38,
        max_drawdown=0.02,
        summary="collecting",
    )

    forecast = build_alpha_validation_forecast(alpha)

    assert forecast.alpha_ready is False
    assert forecast.status == "forecastable"
    assert forecast.estimated_sessions_to_alpha_ready == 5
    assert forecast.limiting_gate == "filled_order_sample"
    filled = [item for item in forecast.items if item.gate == "filled_order_sample"][0]
    assert filled.remaining == 10
    assert filled.estimated_per_session == 2
    assert filled.estimated_sessions == 5


def test_alpha_validation_forecast_marks_ready_strategy_as_zero_sessions():
    alpha = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=True,
        validation_level="paper_validated",
        blockers=[],
        review_day_count=12,
        consecutive_positive_expectancy_days=8,
        filled_order_count=35,
        closed_trade_count=12,
        event_chain_count=200,
        has_real_market_backtest=True,
        latest_expectancy=80,
        average_expectancy=35,
        max_drawdown=0.03,
        summary="validated",
    )

    forecast = build_alpha_validation_forecast(alpha)

    assert forecast.status == "ready"
    assert forecast.estimated_sessions_to_alpha_ready == 0
    assert forecast.limiting_gate is None
    assert all(item.passed for item in forecast.items)


def test_alpha_validation_forecast_exposes_unforecastable_quality_blockers():
    alpha = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=False,
        validation_level="collecting",
        blockers=["average_positive_expectancy"],
        review_day_count=8,
        consecutive_positive_expectancy_days=0,
        filled_order_count=20,
        closed_trade_count=8,
        event_chain_count=100,
        has_real_market_backtest=True,
        latest_expectancy=1,
        average_expectancy=-2,
        max_drawdown=0.01,
        summary="collecting",
    )

    forecast = build_alpha_validation_forecast(alpha)

    assert forecast.status == "blocked"
    assert forecast.estimated_sessions_to_alpha_ready is None
    assert forecast.limiting_gate == "average_positive_expectancy"
    average = [item for item in forecast.items if item.gate == "average_positive_expectancy"][0]
    assert average.estimated_sessions is None
    assert average.reason == "质量门禁需要真实收益改善，不能仅按样本速度估算。"


def test_alpha_validation_forecast_blocks_without_real_market_backtest():
    alpha = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=False,
        validation_level="collecting",
        blockers=["real_market_backtest"],
        review_day_count=10,
        consecutive_positive_expectancy_days=5,
        filled_order_count=34,
        closed_trade_count=12,
        event_chain_count=120,
        has_real_market_backtest=False,
        latest_expectancy=102.91,
        average_expectancy=57.38,
        max_drawdown=0.02,
        summary="collecting",
    )

    forecast = build_alpha_validation_forecast(alpha)

    assert forecast.status == "blocked"
    assert forecast.limiting_gate == "real_market_backtest"
    backtest = [item for item in forecast.items if item.gate == "real_market_backtest"][0]
    assert backtest.passed is False
    assert backtest.estimated_sessions is None
    assert backtest.reason == "需要同策略真实历史回测结果，不能仅靠模拟盘样本估算。"
