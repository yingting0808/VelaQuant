import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.lean_backtest import BacktestParameters, BacktestResult, BacktestStatistics, EquityPoint
from app.services.strategy_catalog import StrategyDefinition


def run_vectorbt_backtest(
    strategy: StrategyDefinition,
    *,
    run_id: str,
    started_at: str,
    parameters: BacktestParameters,
    output_dir: Path,
    readiness_logs: list[str] | None = None,
    market_data_provider: object | None = None,
) -> BacktestResult:
    try:
        import numpy as np
        import pandas as pd
        import vectorbt as vbt
    except ImportError as error:
        return _result(
            strategy=strategy,
            run_id=run_id,
            started_at=started_at,
            parameters=parameters,
            output_dir=output_dir,
            status="unavailable",
            message="vectorbt research backtest is unavailable because the dependency is not installed.",
            logs=[*(readiness_logs or []), str(error)],
        )

    if strategy.id not in {"moving_average_cross", "deterministic_watchlist_v1"}:
        return _result(
            strategy=strategy,
            run_id=run_id,
            started_at=started_at,
            parameters=parameters,
            output_dir=output_dir,
            status="unavailable",
            message=f"vectorbt fallback is not implemented for strategy {strategy.id}.",
            logs=[
                *(readiness_logs or []),
                "Only moving_average_cross and deterministic_watchlist_v1 are supported by the vectorbt research runner.",
            ],
        )

    try:
        if strategy.id == "deterministic_watchlist_v1":
            return _run_watchlist_backtest(
                strategy=strategy,
                run_id=run_id,
                started_at=started_at,
                parameters=parameters,
                output_dir=output_dir,
                readiness_logs=readiness_logs or [],
                market_data_provider=market_data_provider,
                pd=pd,
                np=np,
                vbt=vbt,
            )

        close, data_source, data_warnings = _load_close_series(parameters, market_data_provider, pd, np)
        data_quality = _classify_data_quality(data_source)
        fast_period = int(parameters["fast_period"])
        slow_period = int(parameters["slow_period"])
        if len(close) < slow_period + 5:
            return _result(
                strategy=strategy,
                run_id=run_id,
                started_at=started_at,
                parameters=parameters,
                output_dir=output_dir,
                status="failed",
                message="Not enough price bars to run the moving-average backtest.",
                logs=[
                    *(readiness_logs or []),
                    f"vectorbt received {len(close)} bars; at least {slow_period + 5} bars are required.",
                    *data_warnings,
                ],
            )

        fast = close.rolling(fast_period, min_periods=fast_period).mean()
        slow = close.rolling(slow_period, min_periods=slow_period).mean()
        entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))

        first_trend_day = (fast > slow).idxmax() if (fast > slow).any() else None
        if not bool(entries.any()) and first_trend_day is not None:
            entries.loc[first_trend_day] = True
        if len(exits) > 0:
            exits.iloc[-1] = True

        portfolio = vbt.Portfolio.from_signals(
            close,
            entries,
            exits,
            init_cash=float(parameters["cash"]),
            freq="1D",
        )
        value = portfolio.value()
        statistics = BacktestStatistics(
            total_net_profit=_format_percent(portfolio.total_return()),
            compounding_annual_return=_format_percent(portfolio.annualized_return()),
            sharpe_ratio=_format_number(portfolio.sharpe_ratio()),
            drawdown=_format_percent(abs(float(portfolio.max_drawdown()))),
            win_rate=_format_percent(portfolio.trades.win_rate()),
            total_trades=str(int(portfolio.trades.count())),
        )
        equity = [
            EquityPoint(time=index.date().isoformat(), value=round(float(item), 4))
            for index, item in value.tail(100).items()
        ]
        runtime_message = _vectorbt_runtime_message(readiness_logs)
        logs = [
            *(readiness_logs or []),
            runtime_message,
            f"vectorbt {vbt.__version__} simulated {strategy.id} for {parameters['symbol']}.",
            f"Data source: {data_source}.",
            f"Bars: {len(close)}, entries: {int(entries.sum())}, exits: {int(exits.sum())}.",
            *data_warnings,
        ]
        result = _result(
            strategy=strategy,
            run_id=run_id,
            started_at=started_at,
            parameters=parameters,
            output_dir=output_dir,
            status="success",
            message="Backtest completed with vectorbt research fallback.",
            engine="vectorbt",
            data_source=data_source,
            data_quality=data_quality,
            uses_real_market_data=data_quality == "real_market_data",
            statistics=statistics,
            equity=equity,
            logs=logs,
        )
        _write_vectorbt_artifact(
            output_dir,
            {
                "engine": "vectorbt",
                "strategy_id": strategy.id,
                "parameters": parameters,
                "statistics": statistics.model_dump(),
                "equity": [point.model_dump() for point in equity],
                "logs": logs,
            },
        )
        return result
    except (KeyError, ValueError, TypeError, OSError) as error:
        return _result(
            strategy=strategy,
            run_id=run_id,
            started_at=started_at,
            parameters=parameters,
            output_dir=output_dir,
            status="failed",
            message=f"vectorbt research backtest failed: {error}",
            logs=[*(readiness_logs or []), str(error)],
        )


def _run_watchlist_backtest(
    *,
    strategy: StrategyDefinition,
    run_id: str,
    started_at: str,
    parameters: BacktestParameters,
    output_dir: Path,
    readiness_logs: list[str],
    market_data_provider: object | None,
    pd: Any,
    np: Any,
    vbt: Any,
) -> BacktestResult:
    symbol = parameters["symbol"]
    symbols = [item.strip().upper() for item in symbol.split(",") if item.strip()]
    if not symbols:
        raise ValueError("Watchlist backtest requires at least one ticker.")

    cash = float(parameters["cash"])
    momentum_window = int(parameters.get("momentum_window", "20"))
    min_return = float(parameters.get("min_return", "0.03"))
    exit_window = int(parameters.get("exit_window", "10"))
    required_bars = max(momentum_window, exit_window) + 5
    allocation_cash = cash / len(symbols)
    values = []
    sources: list[str] = []
    data_warnings: list[str] = []
    total_entries = 0
    total_exits = 0
    total_trades = 0
    win_rates: list[float] = []

    for ticker in symbols:
        close, data_source, warnings = _load_close_series(
            parameters,
            market_data_provider,
            pd,
            np,
            symbol=ticker,
            required_bars=required_bars,
        )
        sources.append(data_source)
        data_warnings.extend(warnings)
        momentum = close.pct_change(momentum_window)
        entries = (momentum > min_return) & (momentum.shift(1).fillna(-1.0) <= min_return)
        exit_momentum = close.pct_change(exit_window)
        exits = (exit_momentum < 0) & (exit_momentum.shift(1).fillna(1.0) >= 0)
        if len(exits) > 0:
            exits.iloc[-1] = True

        portfolio = vbt.Portfolio.from_signals(
            close,
            entries,
            exits,
            init_cash=allocation_cash,
            freq="1D",
        )
        value = portfolio.value()
        values.append(value.rename(ticker))
        total_entries += int(entries.sum())
        total_exits += int(exits.sum())
        trades = int(portfolio.trades.count())
        total_trades += trades
        win_rate = _finite_float(portfolio.trades.win_rate())
        if trades > 0 and win_rate is not None:
            win_rates.append(win_rate)

    total_value = pd.concat(values, axis=1).ffill().sum(axis=1)
    returns = total_value.pct_change().dropna()
    total_return = (float(total_value.iloc[-1]) / cash) - 1.0 if len(total_value) else 0.0
    annualized_return = ((1.0 + total_return) ** (252 / max(len(total_value), 1))) - 1.0 if total_return > -1 else None
    sharpe = None
    if len(returns) > 1 and float(returns.std()) > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
    drawdown = ((total_value.cummax() - total_value) / total_value.cummax()).max() if len(total_value) else 0.0
    win_rate = sum(win_rates) / len(win_rates) if win_rates else None
    data_source = _combine_data_sources(sources)
    data_quality = _classify_data_quality(data_source)
    statistics = BacktestStatistics(
        total_net_profit=_format_percent(total_return),
        compounding_annual_return=_format_percent(annualized_return),
        sharpe_ratio=_format_number(sharpe),
        drawdown=_format_percent(drawdown),
        win_rate=_format_percent(win_rate),
        total_trades=str(total_trades),
    )
    equity = [
        EquityPoint(time=index.date().isoformat(), value=round(float(item), 4))
        for index, item in total_value.tail(100).items()
    ]
    logs = [
        *readiness_logs,
        _vectorbt_runtime_message(readiness_logs),
        f"vectorbt {vbt.__version__} simulated {strategy.id} for {', '.join(symbols)}.",
        f"Data source: {data_source}.",
        f"Bars: {len(total_value)}, entries: {total_entries}, exits: {total_exits}.",
        *data_warnings,
    ]
    result = _result(
        strategy=strategy,
        run_id=run_id,
        started_at=started_at,
        parameters=parameters,
        output_dir=output_dir,
        status="success",
        message="Backtest completed with vectorbt research fallback.",
        engine="vectorbt",
        data_source=data_source,
        data_quality=data_quality,
        uses_real_market_data=data_quality == "real_market_data",
        statistics=statistics,
        equity=equity,
        logs=logs,
    )
    _write_vectorbt_artifact(
        output_dir,
        {
            "engine": "vectorbt",
            "strategy_id": strategy.id,
            "parameters": parameters,
            "statistics": statistics.model_dump(),
            "equity": [point.model_dump() for point in equity],
            "logs": logs,
        },
    )
    return result


def _load_close_series(
    parameters: BacktestParameters,
    market_data_provider: object | None,
    pd: Any,
    np: Any,
    *,
    symbol: str | None = None,
    required_bars: int | None = None,
):
    symbol = symbol or parameters["symbol"]
    start_date = parameters["start_date"]
    end_date = parameters["end_date"]
    minimum_bars = required_bars or (int(parameters["slow_period"]) + 5)
    warnings: list[str] = []

    provider = market_data_provider
    if provider is None:
        try:
            from app.data.providers.registry import build_market_data_provider

            provider = build_market_data_provider()
        except (ImportError, RuntimeError, ValueError) as error:
            warnings.append(f"Market data provider unavailable: {error}")

    if provider is not None:
        try:
            history = provider.get_price_history(
                symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )
        except (AttributeError, RuntimeError, ValueError, TypeError) as error:
            history = []
            warnings.append(f"Market data provider failed: {error}")

        close_records = [
            (bar.date, float(bar.close), getattr(bar, "source", "provider"))
            for bar in history
            if getattr(bar, "date", None) and getattr(bar, "close", None) is not None
        ]
        if len(close_records) >= minimum_bars:
            dates = pd.to_datetime([item[0] for item in close_records])
            close = pd.Series([item[1] for item in close_records], index=dates, name=symbol).sort_index()
            source = close_records[0][2] if close_records else "provider"
            return close[~close.index.duplicated(keep="last")], source, warnings
        if close_records:
            warnings.append(
                f"Provider returned only {len(close_records)} bars, so deterministic research data was used."
            )
        else:
            warnings.append("Provider returned no usable price bars, so deterministic research data was used.")

    return _deterministic_close_series(symbol, start_date, end_date, pd, np), "deterministic_research_series", warnings


def _combine_data_sources(sources: list[str]) -> str:
    unique = list(dict.fromkeys(source for source in sources if source))
    if not unique:
        return "unknown"
    if len(unique) == 1:
        return unique[0]
    if all(_classify_data_quality(source) == "real_market_data" for source in unique):
        return "mixed_real_market_data"
    if any(source == "deterministic_research_series" for source in unique):
        return "deterministic_research_series"
    return "mixed_provider_data"


def _vectorbt_runtime_message(readiness_logs: list[str] | None) -> str:
    if readiness_logs:
        return "LEAN runtime is unavailable; vectorbt research runner executed instead."
    return "vectorbt research runner executed for strategy historical replay."


def _deterministic_close_series(symbol: str, start_date: str, end_date: str, pd: Any, np: Any):
    dates = pd.date_range(start=start_date, end=end_date, freq="B")
    if len(dates) == 0:
        raise ValueError("Backtest date range produced no business-day price bars.")

    seed = sum(ord(character) for character in symbol)
    base = 70.0 + float(seed % 170)
    steps = np.arange(len(dates), dtype=float)
    trend = np.linspace(0.0, max(12.0, len(dates) * 0.05), len(dates))
    primary_cycle = np.sin((steps + seed) / 6.0) * base * 0.035
    secondary_cycle = np.cos((steps + seed) / 17.0) * base * 0.015
    close = np.maximum(1.0, base + trend + primary_cycle + secondary_cycle)
    return pd.Series(close, index=dates, name=symbol)


def _result(
    *,
    strategy: StrategyDefinition,
    run_id: str,
    started_at: str,
    parameters: BacktestParameters,
    output_dir: Path,
    status: str,
    message: str,
    logs: list[str],
    engine: str = "vectorbt",
    data_source: str | None = None,
    data_quality: str = "unknown",
    uses_real_market_data: bool = False,
    statistics: BacktestStatistics | None = None,
    equity: list[EquityPoint] | None = None,
) -> BacktestResult:
    completed_at = _utc_now()
    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    return BacktestResult(
        run_id=run_id,
        strategy_id=strategy.id,
        status=status,
        engine=engine,
        data_source=data_source,
        data_quality=data_quality,
        uses_real_market_data=uses_real_market_data,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round((completed - started).total_seconds(), 3),
        message=message,
        parameters=parameters,
        statistics=statistics or BacktestStatistics(),
        equity=equity or [],
        logs=logs,
        output_directory=_safe_output_path(output_dir),
    )


def _classify_data_quality(data_source: str) -> str:
    normalized = data_source.strip().lower()
    if normalized == "deterministic_research_series":
        return "deterministic_research_series"
    if normalized == "mock":
        return "mock_data"
    if normalized == "mixed_real_market_data":
        return "real_market_data"
    if normalized.startswith(("openbb_", "alpaca", "polygon")):
        return "real_market_data"
    return "unknown"


def _format_percent(value: object) -> str | None:
    number = _finite_float(value)
    if number is None:
        return None
    return f"{number * 100:.2f}%"


def _format_number(value: object) -> str | None:
    number = _finite_float(value)
    if number is None:
        return None
    return f"{number:.2f}"


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _safe_output_path(output_dir: Path) -> str:
    from app.services.lean_backtest import API_ROOT

    try:
        return output_dir.relative_to(API_ROOT).as_posix()
    except ValueError:
        return output_dir.name


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_vectorbt_artifact(output_dir: Path, payload: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "vectorbt-result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
