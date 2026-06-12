import json
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

from app.services.lean_backtest import (
    BacktestResult,
    read_backtest_history,
    read_latest_backtest,
    run_lean_backtest,
)
from app.services.strategy_lab import StrategyLabStatus, StrategyToolStatus


def ready_status() -> StrategyLabStatus:
    return StrategyLabStatus(
        can_run_backtests=True,
        summary="ready",
        tools=[
            StrategyToolStatus(name="Docker CLI", available=True, version="Docker version test", message="ready"),
            StrategyToolStatus(name="LEAN CLI", available=True, version="lean test", message="ready"),
        ],
    )


def unready_status() -> StrategyLabStatus:
    return StrategyLabStatus(
        can_run_backtests=False,
        summary="not ready",
        tools=[
            StrategyToolStatus(name="Docker CLI", available=False, version=None, message="Docker missing"),
            StrategyToolStatus(name="LEAN CLI", available=False, version=None, message="LEAN missing"),
        ],
    )


def write_catalog(tmp_path: Path) -> Path:
    project = tmp_path / "lean-workspace" / "MovingAverageCross"
    project.mkdir(parents=True)
    (project / "config.json").write_text(
        json.dumps(
            {
                "algorithm-language": "Python",
                "parameters": {
                    "symbol": "AAPL",
                    "start_date": "2020-01-01",
                    "end_date": "2021-01-01",
                    "cash": "100000",
                    "fast_period": "20",
                    "slow_period": "50",
                },
            }
        ),
        encoding="utf-8",
    )
    catalog = tmp_path / "lean-workspace" / "strategies.json"
    catalog.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "moving_average_cross",
                        "name": "MovingAverageCross",
                        "description": "fixture",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": "MovingAverageCross",
                        "enabled": True,
                        "parameters": [
                            {"name": "symbol", "label": "Ticker", "kind": "ticker", "default": "AAPL", "required": True},
                            {
                                "name": "start_date",
                                "label": "Start Date",
                                "kind": "date",
                                "default": "2020-01-01",
                                "required": True,
                            },
                            {
                                "name": "end_date",
                                "label": "End Date",
                                "kind": "date",
                                "default": "2021-01-01",
                                "required": True,
                            },
                            {
                                "name": "cash",
                                "label": "Initial Cash",
                                "kind": "number",
                                "default": "100000",
                                "min": 1000,
                                "max": 1000000000,
                                "required": True,
                            },
                            {
                                "name": "fast_period",
                                "label": "Fast SMA",
                                "kind": "integer",
                                "default": "20",
                                "min": 2,
                                "max": 400,
                                "required": True,
                            },
                            {
                                "name": "slow_period",
                                "label": "Slow SMA",
                                "kind": "integer",
                                "default": "50",
                                "min": 3,
                                "max": 600,
                                "required": True,
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return catalog


def write_result_json(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "1710698424.json").write_text(
        json.dumps(
            {
                "statistics": {
                    "Total Net Profit": "12.34%",
                    "Compounding Annual Return": "8.10%",
                    "Sharpe Ratio": "0.72",
                    "Drawdown": "15.20%",
                    "Win Rate": "48%",
                    "Total Trades": "24",
                },
                "charts": {
                    "Strategy Equity": {
                        "series": {
                            "Equity": {
                                "values": [
                                    {"x": "2020-01-01", "y": 100000.0},
                                    {"x": "2020-01-02", "y": 100250.0},
                                ]
                            }
                        }
                    }
                },
                "orders": {},
            }
        ),
        encoding="utf-8",
    )


def test_run_lean_backtest_success_parses_statistics_and_saves_latest(tmp_path: Path):
    catalog = write_catalog(tmp_path)
    runtime_root = tmp_path / "runtime"

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        assert command[0:3] == ["lean", "backtest", "MovingAverageCross"]
        assert command[3] == "--output"
        write_result_json(Path(command[4]))
        assert cwd.parent.name == "workspaces"
        config_payload = json.loads((cwd / "MovingAverageCross" / "config.json").read_text(encoding="utf-8"))
        assert config_payload["parameters"]["symbol"] == "AAPL"
        assert config_payload["parameters"]["fast_period"] == "20"
        assert timeout == 180.0
        return CompletedProcess(command, 0, stdout="TRACE:: Backtest completed", stderr="")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=runtime_root,
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "success"
    assert result.statistics.total_net_profit == "12.34%"
    assert result.statistics.sharpe_ratio == "0.72"
    assert result.equity[0].value == 100000.0
    assert result.parameters["symbol"] == "AAPL"
    assert result.parameters["slow_period"] == "50"
    assert result.logs == ["TRACE:: Backtest completed"]
    assert read_latest_backtest(runtime_root=runtime_root) == result
    assert read_backtest_history(runtime_root=runtime_root)[0].run_id == result.run_id


def test_run_lean_backtest_writes_overrides_to_runtime_config_without_mutating_source(tmp_path: Path):
    catalog = write_catalog(tmp_path)
    runtime_root = tmp_path / "runtime"
    source_config = catalog.parent / "MovingAverageCross" / "config.json"

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        config_payload = json.loads((cwd / "MovingAverageCross" / "config.json").read_text(encoding="utf-8"))
        assert config_payload["parameters"] == {
            "symbol": "MSFT",
            "start_date": "2020-02-01",
            "end_date": "2020-12-31",
            "cash": "250000",
            "fast_period": "10",
            "slow_period": "30",
        }
        write_result_json(Path(command[4]))
        return CompletedProcess(command, 0, stdout="", stderr="")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=runtime_root,
        command_runner=runner,
        status_provider=ready_status,
        parameter_overrides={
            "symbol": "msft",
            "start_date": "2020-02-01",
            "end_date": "2020-12-31",
            "cash": "250000",
            "fast_period": "10",
            "slow_period": "30",
        },
    )

    assert result.status == "success"
    assert result.parameters["symbol"] == "MSFT"
    assert json.loads(source_config.read_text(encoding="utf-8"))["parameters"]["symbol"] == "AAPL"


def test_run_lean_backtest_rejects_invalid_ticker_parameter(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    try:
        run_lean_backtest(
            "moving_average_cross",
            catalog_path=catalog,
            runtime_root=tmp_path / "runtime",
            command_runner=lambda command, cwd, timeout: CompletedProcess(command, 0),
            status_provider=ready_status,
            parameter_overrides={"symbol": "bad ticker"},
        )
    except ValueError as error:
        assert "Invalid ticker" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_run_lean_backtest_rejects_start_date_after_end_date(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    try:
        run_lean_backtest(
            "moving_average_cross",
            catalog_path=catalog,
            runtime_root=tmp_path / "runtime",
            command_runner=lambda command, cwd, timeout: CompletedProcess(command, 0),
            status_provider=ready_status,
            parameter_overrides={"start_date": "2021-01-01", "end_date": "2020-01-01"},
        )
    except ValueError as error:
        assert "start_date must be before end_date" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_run_lean_backtest_rejects_fast_period_not_less_than_slow_period(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    try:
        run_lean_backtest(
            "moving_average_cross",
            catalog_path=catalog,
            runtime_root=tmp_path / "runtime",
            command_runner=lambda command, cwd, timeout: CompletedProcess(command, 0),
            status_provider=ready_status,
            parameter_overrides={"fast_period": "50", "slow_period": "50"},
        )
    except ValueError as error:
        assert "fast_period must be less than slow_period" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_run_lean_backtest_success_preserves_zero_statistics_and_equity(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        output_dir = Path(command[4])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "1710698424.json").write_text(
            json.dumps(
                {
                    "statistics": {
                        "Total Net Profit": 0,
                        "Sharpe Ratio": 0,
                    },
                    "charts": {
                        "Strategy Equity": {
                            "series": {
                                "Equity": {
                                    "values": [
                                        {"x": "2020-01-01", "y": 0},
                                    ]
                                }
                            }
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return CompletedProcess(command, 0, stdout="", stderr="")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "success"
    assert result.statistics.total_net_profit == "0"
    assert result.statistics.sharpe_ratio == "0"
    assert result.equity[0].time == "2020-01-01"
    assert result.equity[0].value == 0.0


def test_run_lean_backtest_returns_unavailable_without_calling_runner(tmp_path: Path):
    catalog = write_catalog(tmp_path)
    runtime_root = tmp_path / "runtime"

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        raise AssertionError("runner should not be called")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=runtime_root,
        command_runner=runner,
        status_provider=unready_status,
    )

    assert result.status == "unavailable"
    assert "not ready" in result.message
    assert "Docker missing" in result.logs
    assert result.parameters["symbol"] == "AAPL"
    assert not (runtime_root / "workspaces").exists()
    assert read_backtest_history(runtime_root=runtime_root)[0].status == "unavailable"


def test_run_lean_backtest_returns_failed_for_nonzero_exit(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout="TRACE:: starting", stderr="data missing")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "failed"
    assert "exit code 1" in result.message
    assert result.logs[-1] == "data missing"


def test_run_lean_backtest_returns_tail_logs_for_nonzero_exit(tmp_path: Path):
    catalog = write_catalog(tmp_path)
    stdout = "\n".join(f"stdout-{index}" for index in range(100))
    stderr = "\n".join(f"stderr-{index}" for index in range(100))

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout=stdout, stderr=stderr)

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "failed"
    assert len(result.logs) == 120
    assert result.logs[0] == "stdout-80"
    assert "stderr-0" in result.logs
    assert result.logs[-1] == "stderr-99"


def test_run_lean_backtest_returns_failed_when_runner_cannot_start(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        raise FileNotFoundError("lean executable missing")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "failed"
    assert "lean executable missing" in result.message
    assert result.logs == ["lean executable missing"]


def test_run_lean_backtest_returns_failed_when_runner_raises_os_error(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        raise OSError("permission denied")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "failed"
    assert "permission denied" in result.message
    assert result.logs == ["permission denied"]


def test_run_lean_backtest_returns_malformed_result_for_unreadable_json(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        output_dir = Path(command[4])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "1710698424.json").write_bytes(b"\xff\xfe\x00")
        return CompletedProcess(command, 0, stdout="TRACE:: done", stderr="")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "malformed_result"
    assert "No LEAN result JSON" in result.message


def test_run_lean_backtest_uses_unique_run_id_for_rapid_repeated_runs(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        write_result_json(Path(command[4]))
        return CompletedProcess(command, 0, stdout="", stderr="")

    first = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )
    second = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert first.run_id != second.run_id


def test_run_lean_backtest_returns_timeout_when_runner_times_out(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        raise TimeoutExpired(command, timeout)

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "timeout"
    assert "timed out" in result.message


def test_run_lean_backtest_returns_malformed_result_when_json_is_missing(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        Path(command[4]).mkdir(parents=True, exist_ok=True)
        return CompletedProcess(command, 0, stdout="TRACE:: done", stderr="")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=ready_status,
    )

    assert result.status == "malformed_result"
    assert "No LEAN result JSON" in result.message


def test_read_latest_backtest_returns_none_when_missing(tmp_path: Path):
    assert read_latest_backtest(runtime_root=tmp_path / "runtime") is None


def test_read_latest_backtest_returns_none_when_json_is_corrupt(tmp_path: Path):
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "latest-backtest.json").write_text("{not-json", encoding="utf-8")

    assert read_latest_backtest(runtime_root=runtime_root) is None


def test_read_backtest_history_returns_empty_list_when_missing_or_corrupt(tmp_path: Path):
    runtime_root = tmp_path / "runtime"
    assert read_backtest_history(runtime_root=runtime_root) == []

    runtime_root.mkdir()
    (runtime_root / "history.json").write_text("{not-json", encoding="utf-8")

    assert read_backtest_history(runtime_root=runtime_root) == []


def test_backtest_history_keeps_newest_result_first_and_honors_limit(tmp_path: Path):
    catalog = write_catalog(tmp_path)
    runtime_root = tmp_path / "runtime"

    def success_runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        write_result_json(Path(command[4]))
        return CompletedProcess(command, 0, stdout="success", stderr="")

    def failed_runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout="", stderr="failed")

    first = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=runtime_root,
        command_runner=success_runner,
        status_provider=ready_status,
    )
    second = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=runtime_root,
        command_runner=failed_runner,
        status_provider=ready_status,
        parameter_overrides={"symbol": "MSFT"},
    )

    history = read_backtest_history(runtime_root=runtime_root)
    assert [item.run_id for item in history] == [second.run_id, first.run_id]
    assert history[0].status == "failed"
    assert history[0].parameters["symbol"] == "MSFT"
    assert read_backtest_history(runtime_root=runtime_root, limit=1) == [history[0]]


def test_unknown_strategy_id_raises_value_error(tmp_path: Path):
    catalog = write_catalog(tmp_path)

    try:
        run_lean_backtest(
            "unknown",
            catalog_path=catalog,
            runtime_root=tmp_path / "runtime",
            command_runner=lambda command, cwd, timeout: CompletedProcess(command, 0),
            status_provider=ready_status,
        )
    except ValueError as error:
        assert "Unknown strategy_id" in str(error)
    else:
        raise AssertionError("expected ValueError")
