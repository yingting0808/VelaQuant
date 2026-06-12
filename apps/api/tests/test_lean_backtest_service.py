import json
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

from app.services.lean_backtest import (
    BacktestResult,
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
        assert cwd.name == "lean-workspace"
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
    assert result.logs == ["TRACE:: Backtest completed"]
    assert read_latest_backtest(runtime_root=runtime_root) == result


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

    def runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        raise AssertionError("runner should not be called")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog,
        runtime_root=tmp_path / "runtime",
        command_runner=runner,
        status_provider=unready_status,
    )

    assert result.status == "unavailable"
    assert "not ready" in result.message
    assert "Docker missing" in result.logs


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
