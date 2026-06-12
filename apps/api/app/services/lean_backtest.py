import json
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.services.strategy_catalog import DEFAULT_CATALOG_PATH, StrategyDefinition, get_strategy_by_id
from app.services.strategy_lab import StrategyLabStatus, get_strategy_lab_status


API_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_ROOT = API_ROOT / ".runtime" / "strategy-lab"

BacktestState = Literal["success", "unavailable", "failed", "timeout", "malformed_result"]
BacktestParameters = dict[str, str]
CommandRunner = Callable[[list[str], Path, float], CompletedProcess[str]]
StatusProvider = Callable[[], StrategyLabStatus]


class BacktestParameterValidationError(ValueError):
    pass


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
    parameters: BacktestParameters = Field(default_factory=dict)
    statistics: BacktestStatistics = Field(default_factory=BacktestStatistics)
    equity: list[EquityPoint] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    output_directory: str


class BacktestHistoryItem(BaseModel):
    run_id: str
    strategy_id: str
    status: BacktestState
    started_at: str
    completed_at: str
    duration_seconds: float
    parameters: BacktestParameters = Field(default_factory=dict)
    statistics: BacktestStatistics = Field(default_factory=BacktestStatistics)

    @classmethod
    def from_result(cls, result: BacktestResult) -> "BacktestHistoryItem":
        return cls(
            run_id=result.run_id,
            strategy_id=result.strategy_id,
            status=result.status,
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_seconds=result.duration_seconds,
            parameters=result.parameters,
            statistics=result.statistics,
        )


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
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _run_id(strategy_id: str, started_at: str) -> str:
    compact = started_at.replace("-", "").replace(":", "").replace(".", "").replace("+00:00", "Z")
    compact = compact.replace("T", "T").replace("Z", "Z")
    return f"{compact}-{strategy_id}"


def _tail_lines(stdout: str | None, stderr: str | None, limit: int | None = 120) -> list[str]:
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


def _runtime_workspace_directory(runtime_root: Path, run_id: str) -> Path:
    return runtime_root / "workspaces" / run_id


def _latest_path(runtime_root: Path) -> Path:
    return runtime_root / "latest-backtest.json"


def _history_path(runtime_root: Path) -> Path:
    return runtime_root / "history.json"


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
    parameters: BacktestParameters,
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
        parameters=parameters,
        logs=logs,
        output_directory=_safe_output_path(output_dir),
    )


def _normalize_backtest_parameters(
    strategy: StrategyDefinition,
    overrides: dict[str, str] | None,
) -> BacktestParameters:
    definitions = {parameter.name: parameter for parameter in strategy.parameters}
    normalized_overrides = overrides or {}
    for key in normalized_overrides:
        if key not in definitions:
            raise BacktestParameterValidationError(f"Unsupported strategy parameter: {key}")

    parameters: BacktestParameters = {}
    for definition in strategy.parameters:
        raw_value = str(normalized_overrides.get(definition.name, definition.default)).strip()
        if not raw_value and definition.required:
            raise BacktestParameterValidationError(f"Missing required strategy parameter: {definition.name}")
        if not raw_value:
            continue

        if definition.kind == "ticker":
            parameters[definition.name] = _normalize_ticker(definition.name, raw_value)
        elif definition.kind == "date":
            parameters[definition.name] = _normalize_date(definition.name, raw_value).isoformat()
        elif definition.kind == "integer":
            parameters[definition.name] = str(_normalize_integer(definition.name, raw_value, definition.min, definition.max))
        elif definition.kind == "number":
            parameters[definition.name] = _normalize_number(definition.name, raw_value, definition.min, definition.max)

    if "start_date" in parameters and "end_date" in parameters:
        start = _normalize_date("start_date", parameters["start_date"])
        end = _normalize_date("end_date", parameters["end_date"])
        if start >= end:
            raise BacktestParameterValidationError("start_date must be before end_date")

    if "fast_period" in parameters and "slow_period" in parameters:
        fast = int(parameters["fast_period"])
        slow = int(parameters["slow_period"])
        if fast >= slow:
            raise BacktestParameterValidationError("fast_period must be less than slow_period")

    return parameters


def _normalize_ticker(name: str, value: str) -> str:
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.-]{1,12}", normalized):
        raise BacktestParameterValidationError(f"Invalid ticker parameter {name}: {value}")
    return normalized


def _normalize_date(name: str, value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise BacktestParameterValidationError(f"Invalid date parameter {name}: {value}") from error


def _normalize_integer(name: str, value: str, minimum: float | None, maximum: float | None) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise BacktestParameterValidationError(f"Invalid integer parameter {name}: {value}") from error
    if minimum is not None and parsed < minimum:
        raise BacktestParameterValidationError(f"{name} must be greater than or equal to {int(minimum)}")
    if maximum is not None and parsed > maximum:
        raise BacktestParameterValidationError(f"{name} must be less than or equal to {int(maximum)}")
    return parsed


def _normalize_number(name: str, value: str, minimum: float | None, maximum: float | None) -> str:
    try:
        parsed = float(value)
    except ValueError as error:
        raise BacktestParameterValidationError(f"Invalid number parameter {name}: {value}") from error
    if minimum is not None and parsed < minimum:
        raise BacktestParameterValidationError(f"{name} must be greater than or equal to {minimum:g}")
    if maximum is not None and parsed > maximum:
        raise BacktestParameterValidationError(f"{name} must be less than or equal to {maximum:g}")
    return value.strip()


def _prepare_runtime_workspace(
    *,
    strategy: StrategyDefinition,
    run_id: str,
    parameters: BacktestParameters,
    runtime_root: Path,
) -> Path:
    workspace_dir = _runtime_workspace_directory(runtime_root, run_id)
    project_dir = workspace_dir / strategy.project_path.name
    workspace_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(strategy.project_path, project_dir, dirs_exist_ok=True)
    _write_project_parameters(project_dir / "config.json", parameters)
    return workspace_dir


def _write_project_parameters(config_path: Path, parameters: BacktestParameters) -> None:
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
    else:
        payload = {}
    payload["parameters"] = parameters
    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_lean_backtest(
    strategy_id: str,
    *,
    parameter_overrides: dict[str, str] | None = None,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    command_runner: CommandRunner = default_command_runner,
    status_provider: StatusProvider = get_strategy_lab_status,
    timeout_seconds: float = 180.0,
) -> BacktestResult:
    strategy = get_strategy_by_id(strategy_id, catalog_path=catalog_path)
    parameters = _normalize_backtest_parameters(strategy, parameter_overrides)
    started_at = _utc_now()
    run_id = _run_id(strategy.id, started_at)
    output_dir = _runtime_output_directory(runtime_root, run_id)

    readiness = status_provider()
    if not readiness.can_run_backtests:
        result = _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="unavailable",
            started_at=started_at,
            completed_at=_utc_now(),
            message=readiness.summary,
            parameters=parameters,
            logs=[tool.message for tool in readiness.tools if not tool.available],
            output_dir=output_dir,
        )
        _save_result(result, runtime_root)
        return result

    try:
        workspace_dir = _prepare_runtime_workspace(
            strategy=strategy,
            run_id=run_id,
            parameters=parameters,
            runtime_root=runtime_root,
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        message = str(error) or error.__class__.__name__
        result = _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="failed",
            started_at=started_at,
            completed_at=_utc_now(),
            message=f"LEAN runtime workspace could not be prepared: {message}",
            parameters=parameters,
            logs=[message],
            output_dir=output_dir,
        )
        _save_result(result, runtime_root)
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
            parameters=parameters,
            logs=[],
            output_dir=output_dir,
        )
        _save_result(result, runtime_root)
        return result
    except OSError as error:
        message = str(error) or error.__class__.__name__
        result = _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="failed",
            started_at=started_at,
            completed_at=_utc_now(),
            message=f"LEAN backtest could not be started: {message}",
            parameters=parameters,
            logs=[message],
            output_dir=output_dir,
        )
        _save_result(result, runtime_root)
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
            parameters=parameters,
            logs=logs,
            output_dir=output_dir,
        )
        _save_result(result, runtime_root)
        return result

    parsed = _parse_backtest_output(strategy, run_id, started_at, output_dir, logs, parameters)
    _save_result(parsed, runtime_root)
    return parsed


def _parse_backtest_output(
    strategy: StrategyDefinition,
    run_id: str,
    started_at: str,
    output_dir: Path,
    logs: list[str],
    parameters: BacktestParameters,
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
            parameters=parameters,
            logs=logs,
            output_dir=output_dir,
        )

    try:
        payload = json.loads(result_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return _empty_result(
            run_id=run_id,
            strategy_id=strategy.id,
            status="malformed_result",
            started_at=started_at,
            completed_at=_utc_now(),
            message="LEAN result JSON could not be parsed.",
            parameters=parameters,
            logs=logs,
            output_dir=output_dir,
        )

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
        parameters=parameters,
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
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
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
    latest_path = _latest_path(runtime_root)
    temp_path = runtime_root / f".{latest_path.name}.{result.run_id}.tmp"
    temp_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    temp_path.replace(latest_path)


def _save_result(result: BacktestResult, runtime_root: Path) -> None:
    _save_latest(result, runtime_root)
    _save_history_item(result, runtime_root)


def _save_history_item(result: BacktestResult, runtime_root: Path, limit: int = 50) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    item = BacktestHistoryItem.from_result(result)
    existing = read_backtest_history(runtime_root=runtime_root, limit=limit)
    history = [item]
    history.extend(existing_item for existing_item in existing if existing_item.run_id != item.run_id)
    history = history[:limit]
    history_path = _history_path(runtime_root)
    temp_path = runtime_root / f".{history_path.name}.{result.run_id}.tmp"
    payload = {"history": [history_item.model_dump() for history_item in history]}
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(history_path)


def read_latest_backtest(runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> BacktestResult | None:
    path = _latest_path(runtime_root)
    if not path.exists():
        return None
    try:
        return BacktestResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValidationError):
        return None


def read_backtest_history(
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    limit: int = 10,
) -> list[BacktestHistoryItem]:
    path = _history_path(runtime_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_history = payload.get("history", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_history, list):
            return []
        parsed = [BacktestHistoryItem.model_validate(item) for item in raw_history]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError):
        return []

    normalized_limit = max(0, limit)
    return parsed[:normalized_limit]
