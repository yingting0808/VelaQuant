import json
from pathlib import Path
from subprocess import CompletedProcess

from app.services.lean_backtest import run_lean_backtest
from app.services.strategy_lab import StrategyLabStatus, StrategyToolStatus


def test_lean_backtest_uses_runtime_lean_config(tmp_path):
    project_dir = tmp_path / "catalog" / "MovingAverageCross"
    project_dir.mkdir(parents=True)
    (project_dir / "config.json").write_text("{}", encoding="utf-8")
    (project_dir / "main.py").write_text("class MovingAverageCross: pass\n", encoding="utf-8")
    catalog_path = tmp_path / "catalog" / "strategies.json"
    catalog_path.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "moving_average_cross",
                        "name": "MovingAverageCross",
                        "description": "Test strategy.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": "MovingAverageCross",
                        "enabled": True,
                        "parameters": [
                            {"name": "symbol", "label": "Ticker", "kind": "ticker", "default": "AAPL"},
                            {"name": "start_date", "label": "Start Date", "kind": "date", "default": "2020-01-01"},
                            {"name": "end_date", "label": "End Date", "kind": "date", "default": "2020-02-01"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def command_runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = cwd
        config_path = Path(command[command.index("--lean-config") + 1])
        captured["lean_config_path"] = config_path
        captured["lean_config"] = json.loads(config_path.read_text(encoding="utf-8"))
        return CompletedProcess(command, 1, "", "intentional failure")

    result = run_lean_backtest(
        "moving_average_cross",
        catalog_path=catalog_path,
        runtime_root=tmp_path / "runtime",
        command_runner=command_runner,
        status_provider=_lean_ready,
        enable_vectorbt_fallback=False,
    )

    assert result.status == "failed"
    assert "--lean-config" in captured["command"]
    assert Path(captured["lean_config_path"]).name == "lean.json"
    assert captured["lean_config"]["data-folder"] == "Data"
    assert captured["lean_config"]["organization-id"] == "00000000000000000000000000000000"
    assert captured["lean_config"]["job-organization-id"] == "00000000000000000000000000000000"
    assert (Path(captured["cwd"]) / "lean.json").exists()
    assert (Path(captured["cwd"]) / "Data").is_dir()


def _lean_ready() -> StrategyLabStatus:
    return StrategyLabStatus(
        can_run_backtests=True,
        summary="ready",
        tools=[
            StrategyToolStatus(name="Docker CLI", available=True, version="docker", message="ok"),
            StrategyToolStatus(name="Docker Compose", available=True, version="compose", message="ok"),
            StrategyToolStatus(name="Docker engine", available=True, version="engine", message="ok"),
            StrategyToolStatus(name="LEAN CLI", available=True, version="lean", message="ok"),
            StrategyToolStatus(name="vectorbt", available=True, version="1.0", message="ok"),
        ],
    )
