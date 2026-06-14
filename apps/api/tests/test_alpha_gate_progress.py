from app.services.alpha_gate_progress import build_alpha_gate_progress
from app.services.alpha_validation import AlphaValidationPayload


def test_alpha_gate_progress_quantifies_remaining_validation_gaps():
    alpha = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=False,
        validation_level="collecting",
        blockers=[
            "review_day_sample",
            "consecutive_positive_expectancy",
            "filled_order_sample",
            "closed_trade_sample",
            "real_market_backtest",
            "average_positive_expectancy",
            "drawdown_limit",
        ],
        review_day_count=3,
        consecutive_positive_expectancy_days=2,
        filled_order_count=12,
        closed_trade_count=4,
        event_chain_count=20,
        has_real_market_backtest=False,
        latest_expectancy=1.5,
        average_expectancy=-0.2,
        max_drawdown=0.18,
        summary="collecting",
    )

    progress = build_alpha_gate_progress(alpha)

    assert progress.alpha_ready is False
    assert progress.total_gates == 9
    assert progress.passed_gates == 2
    assert progress.items[0].gate == "review_day_sample"
    assert progress.items[0].current == 3
    assert progress.items[0].required == 5
    assert progress.items[0].remaining == 2
    drawdown = [item for item in progress.items if item.gate == "drawdown_limit"][0]
    assert drawdown.passed is False
    assert drawdown.current == 0.18
    assert drawdown.required == 0.15
    assert drawdown.remaining == 0.03
    backtest = [item for item in progress.items if item.gate == "real_market_backtest"][0]
    assert backtest.passed is False
    assert backtest.current == 0
    assert backtest.required == 1
    assert "2/9" in progress.summary
