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
    assert progress.total_gates == 10
    assert progress.passed_gates == 3
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
    score_pnl = [item for item in progress.items if item.gate == "score_pnl_inversion_review"][0]
    assert score_pnl.passed is True
    assert score_pnl.current == 0
    assert score_pnl.required == 0
    assert "3/10" in progress.summary


def test_alpha_gate_progress_tracks_score_pnl_inversion_quality_gate():
    alpha = AlphaValidationPayload(
        strategy_id="deterministic_watchlist_v1",
        alpha_ready=False,
        validation_level="collecting",
        blockers=["score_pnl_inversion_review"],
        review_day_count=5,
        consecutive_positive_expectancy_days=5,
        filled_order_count=34,
        closed_trade_count=12,
        event_chain_count=160,
        has_real_market_backtest=True,
        latest_expectancy=12.5,
        average_expectancy=8.2,
        max_drawdown=0.02,
        score_pnl_inversion_count=2,
        summary="collecting",
    )

    progress = build_alpha_gate_progress(alpha)

    score_pnl = [item for item in progress.items if item.gate == "score_pnl_inversion_review"][0]
    assert progress.alpha_ready is False
    assert progress.total_gates == 10
    assert progress.passed_gates == 9
    assert score_pnl.label == "评分盈亏反向"
    assert score_pnl.current == 2
    assert score_pnl.required == 0
    assert score_pnl.remaining == 2
    assert score_pnl.passed is False
