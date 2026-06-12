import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from typing import Literal

from pydantic import BaseModel, Field

from app.services.strategy_catalog import DEFAULT_CATALOG_PATH, StrategyDefinition, get_strategy_by_id
from app.services.strategy_lab import StrategyLabStatus, get_strategy_lab_status


API_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_ROOT = API_ROOT / ".runtime" / "strategy-lab"

BacktestState = Literal["success", "unavailable", "failed", "timeout", "malformed_result"]
CommandRunner = Callable[[list[str], Path, float], CompletedProcess[str]]
StatusProvider = Callable[[], StrategyLabStatus]


class BacktestStatistics(BaseModel):
    total_net_profit: str | None = None
    compounding_annual_return: str | None = None
    sharpe_ratio: str | None = None
    drawdown: str | None = None
    win_rate: str | None = None
    total_trades: str | None = None


class EquityPoint(BaseModel):
    time: str
    value: float


class BacktestResult(BaseModel):
    run_id: str
    strategy_id: str
    status: BacktestState
    started_at: str
    completed_at: str
    duration_seconds: float
    message: str
    statistics: BacktestStatistics = Field(default_factory=BacktestStatistics)
    equity: list[EquityPoint] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    output_directory: str


def default_command_runner(command: list[str], cwd: Path, timeout: float) -> CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        cwd=str(cwd),
        shell=False,
        text=True,
        timeout=timeout,
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id(strategy_id: str, started_at: str) -> str:
    compact = started_at.replace("-", "").replace(":", "").replace("+00:00", "Z")
    compact = compact.replace("T", "T").replace("Z", "Z")
    return f"{compact}-{strategy_id}"


def _tail_lines(stdout: str | None, stderr: str | None, limit: int | None = None) -> list[str]:
    lines = []
    for text in (stdout or "", stderr or ""):
        lines.extend(line.strip() for line in text.splitlines() if line.strip())
    if limit is None:
        return lines
    if limit <= 0:
        return []
    return lines[-limit:]


def _runtime_output_directory(runtime_root: Path, run_id: str) -> Path:
    return runtime_root / "backtests" / run_id


def _latest_path(runtime_root: Path) -> Path:
    return runtime_root / "latest-backtest.json"


def _safe_output_path(output_dir: Path) -> str:
    try:
        return output_dir.relative_to(API_ROOT).as_posix()
    except ValueError:
        return output_dir.name


def _empty_result(
    *,
    run_id: str,
    strategy_id: str,
    status: BacktestState,
    started_at: str,
    completed_at: str,
    message: str,
    logs: list[str],
    output_dir: Path,
) -> BacktestResult:
    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    return BacktestResult(
        run_id=run_id,
        strategy_id=strategy_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round((completed - started).total_seconds(), 3),
        message=message,
        logs=logs,
        output_directory=_safe_output_path(output_dir),
    )


def run_lean_backtest(
    strategy_id: str,
    *,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    command_runner: CommandRunner = default_command_runner,
    status_provider: StatusProvider = get_strategy_lab_status,
    timeout_seconds: float = 180.0,
) -> BacktestResult:
    strategy = get_strategy_by_id(strategy_id, catalog_path=catalog_path)
    started_at = _utc_now()
    run_id = _run_id(strategy.id, started_at)
    output_dir = _runtime_output_directory(runtime_root, run_id)
    workspace_dir = catalog_path.parent

    readiness = status_provider()
    if not readiness.can_run_backtests:
        result = _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="unavailable",
            started_at=started_at,
            completed_at=_utc_now(),
            message=readiness.summary,
            logs=[tool.message for tool in readiness.tools if not tool.available],
            output_dir=output_dir,
        )
        _save_latest(result, runtime_root)
        return result

    command = ["lean", "backtest", strategy.project_path.name, "--output", str(output_dir)]
    try:
        completed = command_runner(command, workspace_dir, timeout_seconds)
    except TimeoutExpired:
        result = _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="timeout",
            started_at=started_at,
            completed_at=_utc_now(),
            message=f"LEAN backtest timed out after {timeout_seconds:.1f}s.",
            logs=[],
            output_dir=output_dir,
        )
        _save_latest(result, runtime_root)
        return result

    logs = _tail_lines(completed.stdout, completed.stderr)
    if completed.returncode != 0:
        result = _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="failed",
            started_at=started_at,
            completed_at=_utc_now(),
            message=f"LEAN backtest returned exit code {completed.returncode}.",
            logs=logs,
            output_dir=output_dir,
        )
        _save_latest(result, runtime_root)
        return result

    parsed = _parse_backtest_output(strategy, run_id, started_at, output_dir, logs)
    _save_latest(parsed, runtime_root)
    return parsed


def _parse_backtest_output(
    strategy: StrategyDefinition,
    run_id: str,
    started_at: str,
    output_dir: Path,
    logs: list[str],
) -> BacktestResult:
    result_json = _find_result_json(output_dir)
    if result_json is None:
        return _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="malformed_result",
            started_at=started_at,
            completed_at=_utc_now(),
            message="No LEAN result JSON could be parsed.",
            logs=logs,
            output_dir=output_dir,
        )

    payload = json.loads(result_json.read_text(encoding="utf-8"))
    statistics = _extract_statistics(payload)
    equity = _extract_equity(payload)
    completed_at = _utc_now()
    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    return BacktestResult(
        run_id=run_id,
        strategy_id=strategy.id,
        status="success",
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round((completed - started).total_seconds(), 3),
        message="Backtest completed.",
        statistics=statistics,
        equity=equity,
        logs=logs,
        output_directory=_safe_output_path(output_dir),
    )


def _find_result_json(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    for candidate in sorted(output_dir.rglob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and any(key in payload for key in ("statistics", "Statistics", "charts", "Charts")):
            return candidate
    return None


def _extract_statistics(payload: dict) -> BacktestStatistics:
    raw = payload.get("statistics") or payload.get("Statistics") or {}
    if not isinstance(raw, dict):
        raw = {}
    orders = payload.get("orders") or payload.get("Orders") or {}
    return BacktestStatistics(
        total_net_profit=_stat(raw, "Total Net Profit"),
        compounding_annual_return=_stat(raw, "Compounding Annual Return"),
        sharpe_ratio=_stat(raw, "Sharpe Ratio"),
        drawdown=_stat(raw, "Drawdown"),
        win_rate=_stat(raw, "Win Rate"),
        total_trades=_stat(raw, "Total Trades") or _order_count(orders),
    )


def _stat(raw: dict, name: str) -> str | None:
    for key in (name, name.lower(), name.replace(" ", "")):
        if key in raw:
            value = raw[key]
            return str(value) if value is not None else None
    return None


def _order_count(orders: object) -> str | None:
    if isinstance(orders, dict):
        return str(len(orders))
    if isinstance(orders, list):
        return str(len(orders))
    return None


def _extract_equity(payload: dict) -> list[EquityPoint]:
    charts = payload.get("charts") or payload.get("Charts") or {}
    if not isinstance(charts, dict):
        return []
    for chart_name in ("Strategy Equity", "Equity", "Portfolio Equity"):
        chart = charts.get(chart_name)
        if not isinstance(chart, dict):
            continue
        series = chart.get("series") or chart.get("Series") or {}
        if not isinstance(series, dict):
            continue
        for series_value in series.values():
            if not isinstance(series_value, dict):
                continue
            values = series_value.get("values") or series_value.get("Values") or []
            points = _equity_points(values)
            if points:
                return points[-100:]
    return []


def _equity_points(values: object) -> list[EquityPoint]:
    if not isinstance(values, list):
        return []
    points: list[EquityPoint] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        time = _first_existing_value(item, ("x", "time", "Time"))
        value = _first_existing_value(item, ("y", "value", "Value"))
        if time is None or value is None:
            continue
        try:
            points.append(EquityPoint(time=str(time), value=float(value)))
        except (TypeError, ValueError):
            continue
    return points


def _first_existing_value(raw: dict, keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _save_latest(result: BacktestResult, runtime_root: Path) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    _latest_path(runtime_root).write_text(result.model_dump_json(indent=2), encoding="utf-8")


def read_latest_backtest(runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> BacktestResult | None:
    path = _latest_path(runtime_root)
    if not path.exists():
        return None
    return BacktestResult.model_validate_json(path.read_text(encoding="utf-8"))
