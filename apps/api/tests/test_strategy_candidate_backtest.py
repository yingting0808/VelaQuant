from app.services.lean_backtest import BacktestResult, BacktestStatistics
from app.services.strategy_candidate_backtest import run_strategy_candidate_backtests


def test_candidate_backtests_rank_real_profitable_candidates_and_explain_reasons():
    calls = []

    def fake_runner(strategy_id: str, *, parameter_overrides=None, market_data_provider=None):
        calls.append((strategy_id, dict(parameter_overrides or {})))
        ticker = parameter_overrides["symbol"]
        if ticker == "NVDA":
            return _result(ticker, profit="42.00%", sharpe="1.80", drawdown="12.00%", trades="9")
        if ticker == "MSFT":
            return _result(ticker, profit="18.00%", sharpe="0.90", drawdown="6.00%", trades="5")
        return _result(ticker, profit="-3.00%", sharpe="-0.20", drawdown="9.00%", trades="4")

    payload = run_strategy_candidate_backtests(
        strategy_id="deterministic_watchlist_v1",
        tickers=["aapl", " nvda ", "MSFT", "nvda"],
        parameter_overrides={"start_date": "2020-01-01", "end_date": "2021-01-01", "cash": "100000"},
        backtest_runner=fake_runner,
    )

    assert [call[1]["symbol"] for call in calls] == ["AAPL", "NVDA", "MSFT"]
    assert all(call[0] == "deterministic_watchlist_v1" for call in calls)
    assert payload.strategy_id == "deterministic_watchlist_v1"
    assert payload.candidate_count == 3
    assert payload.best_ticker == "NVDA"
    assert payload.real_market_candidate_count == 3
    assert [item.ticker for item in payload.items] == ["NVDA", "MSFT", "AAPL"]
    assert payload.items[0].rank == 1
    assert payload.items[0].recommendation == "candidate"
    assert payload.items[0].score > payload.items[1].score
    assert "真实历史数据" in payload.items[0].reason
    assert "收益为正" in payload.items[0].reason
    assert payload.items[-1].recommendation == "reject"
    assert "收益未通过" in payload.items[-1].reason


def test_candidate_backtests_demote_non_real_data_even_when_profit_is_positive():
    def fake_runner(strategy_id: str, *, parameter_overrides=None, market_data_provider=None):
        ticker = parameter_overrides["symbol"]
        if ticker == "AAPL":
            return _result(ticker, profit="30.00%", sharpe="1.20", drawdown="10.00%", trades="6", real=False)
        return _result(ticker, profit="5.00%", sharpe="0.40", drawdown="8.00%", trades="3")

    payload = run_strategy_candidate_backtests(
        strategy_id="deterministic_watchlist_v1",
        tickers=["AAPL", "MSFT"],
        backtest_runner=fake_runner,
    )

    assert [item.ticker for item in payload.items] == ["MSFT", "AAPL"]
    assert payload.items[0].uses_real_market_data is True
    assert payload.items[1].recommendation == "watch"
    assert "不作为候选" in payload.items[1].reason


def test_candidate_backtests_reject_blank_or_duplicate_only_input():
    try:
        run_strategy_candidate_backtests(tickers=[" ", "aapl", "AAPL"], backtest_runner=lambda *args, **kwargs: None)
    except ValueError as error:
        assert "at least two unique tickers" in str(error)
    else:
        raise AssertionError("expected ValueError")


def _result(
    ticker: str,
    *,
    profit: str,
    sharpe: str,
    drawdown: str,
    trades: str,
    real: bool = True,
) -> BacktestResult:
    return BacktestResult(
        run_id=f"run-{ticker}",
        strategy_id="deterministic_watchlist_v1",
        status="success",
        engine="vectorbt",
        data_source="openbb_yfinance" if real else "deterministic_research_series",
        data_quality="real_market_data" if real else "deterministic_research_series",
        uses_real_market_data=real,
        started_at="2026-06-14T00:00:00Z",
        completed_at="2026-06-14T00:00:01Z",
        duration_seconds=1,
        message="ok",
        parameters={"symbol": ticker},
        statistics=BacktestStatistics(
            total_net_profit=profit,
            sharpe_ratio=sharpe,
            drawdown=drawdown,
            total_trades=trades,
        ),
        equity=[],
        logs=[],
        output_directory=f"runtime/{ticker}",
    )
