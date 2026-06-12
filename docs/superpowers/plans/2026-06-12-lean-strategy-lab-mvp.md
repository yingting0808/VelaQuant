# LEAN Strategy Lab MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local QuantConnect LEAN backtest loop to Strategy Lab with a cataloged sample strategy, safe backend execution, result parsing, and frontend result display.

**Architecture:** Keep LEAN integration behind backend service boundaries: `strategy_catalog.py` owns the strategy whitelist, `lean_backtest.py` owns command execution and result parsing, and MVP routes expose structured payloads. The frontend remains a client of stable API helpers and renders readiness, catalog, latest result, and run-result states without issuing shell commands or knowing local paths.

**Tech Stack:** FastAPI, Pydantic, pytest, subprocess, QuantConnect LEAN CLI, Docker, Next.js App Router, React, TypeScript, Playwright.

---

## Execution Notes

- Worktree: `D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab`
- Branch: `codex/lean-strategy-lab`
- Design spec: `docs/superpowers/specs/2026-06-12-lean-strategy-lab-mvp-design.md`
- Keep LEAN optional at runtime. Automated tests must not call real Docker, real LEAN CLI, or the network.
- Only run cataloged enabled strategies. Do not accept user strategy code or arbitrary command text.
- Do not add broker connections, live trading, order placement, cloud backtests, or AI-generated strategy execution.
- QuantConnect docs confirm `lean backtest` runs local backtests through Docker and supports `--output` for the result directory.

## File Structure

- Modify `.gitignore`: ignore `apps/api/.runtime/`.
- Create `apps/api/lean-workspace/strategies.json`: checked-in strategy metadata catalog.
- Create `apps/api/lean-workspace/MovingAverageCross/config.json`: minimal LEAN project config metadata.
- Create `apps/api/lean-workspace/MovingAverageCross/main.py`: sample AAPL moving-average crossover algorithm.
- Create `apps/api/app/services/strategy_catalog.py`: read, validate, and expose enabled strategy metadata.
- Create `apps/api/app/services/lean_backtest.py`: execute cataloged LEAN backtests, parse output JSON, save and read latest result.
- Modify `apps/api/app/api/routes/mvp.py`: add strategy catalog, run backtest, and latest backtest endpoints.
- Create `apps/api/tests/test_strategy_catalog.py`: catalog tests.
- Create `apps/api/tests/test_lean_backtest_service.py`: runner, parser, latest, and failure-state tests.
- Modify `apps/api/tests/test_mvp_routes.py`: API endpoint tests with monkeypatched services.
- Modify `apps/web/src/lib/client-api.ts`: strategy/backtest payload types, validators, fallback payloads, fetch helpers.
- Create `apps/web/src/components/strategy-backtest-panel.tsx`: client component for catalog, run action, latest result, metrics, logs.
- Modify `apps/web/src/app/strategy-lab/page.tsx`: render the new panel below readiness.
- Modify `apps/web/src/app/styles.css`: compact Strategy Lab metric and log styles.
- Modify `apps/web/tests/mvp.spec.ts`: Strategy Lab E2E tests for success and failure payloads.

---

### Task 1: Strategy Catalog and Sample LEAN Project

**Files:**
- Modify: `.gitignore`
- Create: `apps/api/lean-workspace/strategies.json`
- Create: `apps/api/lean-workspace/MovingAverageCross/config.json`
- Create: `apps/api/lean-workspace/MovingAverageCross/main.py`
- Create: `apps/api/app/services/strategy_catalog.py`
- Test: `apps/api/tests/test_strategy_catalog.py`

- [ ] **Step 1: Write failing catalog tests**

Create `apps/api/tests/test_strategy_catalog.py`:

```python
import json
from pathlib import Path

import pytest

from app.services.strategy_catalog import (
    StrategyDefinition,
    get_strategy_by_id,
    load_enabled_strategies,
)


def test_load_enabled_strategies_returns_checked_in_moving_average_strategy():
    strategies = load_enabled_strategies()

    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy.id == "moving_average_cross"
    assert strategy.name == "MovingAverageCross"
    assert strategy.language == "Python"
    assert strategy.default_symbol == "AAPL"
    assert strategy.enabled is True
    assert strategy.project_path.name == "MovingAverageCross"


def test_get_strategy_by_id_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown strategy_id"):
        get_strategy_by_id("not_real")


def test_catalog_filters_disabled_strategies(tmp_path: Path):
    catalog = tmp_path / "strategies.json"
    catalog.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "id": "enabled_one",
                        "name": "EnabledOne",
                        "description": "Enabled fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "AAPL",
                        "resolution": "Daily",
                        "project_path": "EnabledOne",
                        "enabled": True,
                    },
                    {
                        "id": "disabled_one",
                        "name": "DisabledOne",
                        "description": "Disabled fixture.",
                        "language": "Python",
                        "asset_class": "US Equity",
                        "default_symbol": "MSFT",
                        "resolution": "Daily",
                        "project_path": "DisabledOne",
                        "enabled": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    strategies = load_enabled_strategies(catalog_path=catalog)

    assert [strategy.id for strategy in strategies] == ["enabled_one"]
    assert isinstance(strategies[0], StrategyDefinition)
```

- [ ] **Step 2: Run catalog tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest tests/test_strategy_catalog.py -v
```

Expected: FAIL because `app.services.strategy_catalog` does not exist.

- [ ] **Step 3: Add runtime ignore rule**

Append to `.gitignore`:

```gitignore
apps/api/.runtime/
```

- [ ] **Step 4: Add strategy catalog metadata**

Create `apps/api/lean-workspace/strategies.json`:

```json
{
  "strategies": [
    {
      "id": "moving_average_cross",
      "name": "MovingAverageCross",
      "description": "AAPL daily moving average crossover sample for local LEAN validation.",
      "language": "Python",
      "asset_class": "US Equity",
      "default_symbol": "AAPL",
      "resolution": "Daily",
      "project_path": "MovingAverageCross",
      "enabled": true
    }
  ]
}
```

- [ ] **Step 5: Add minimal LEAN project config**

Create `apps/api/lean-workspace/MovingAverageCross/config.json`:

```json
{
  "algorithm-language": "Python",
  "parameters": {},
  "description": "AAPL daily moving average crossover sample for local LEAN validation."
}
```

- [ ] **Step 6: Add sample LEAN algorithm**

Create `apps/api/lean-workspace/MovingAverageCross/main.py`:

```python
from AlgorithmImports import *


class MovingAverageCrossAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2021, 1, 1)
        self.SetCash(100000)

        self.symbol = self.AddEquity("AAPL", Resolution.Daily).Symbol
        self.fast = self.SMA(self.symbol, 20, Resolution.Daily)
        self.slow = self.SMA(self.symbol, 50, Resolution.Daily)
        self.previous_fast_above_slow = None
        self.SetWarmUp(50, Resolution.Daily)

    def OnData(self, data):
        if self.IsWarmingUp or not self.fast.IsReady or not self.slow.IsReady:
            return

        fast_above_slow = self.fast.Current.Value > self.slow.Current.Value
        if self.previous_fast_above_slow is None:
            self.previous_fast_above_slow = fast_above_slow
            return

        if fast_above_slow and not self.previous_fast_above_slow:
            self.SetHoldings(self.symbol, 1.0)
        elif not fast_above_slow and self.previous_fast_above_slow:
            self.Liquidate(self.symbol)

        self.previous_fast_above_slow = fast_above_slow
```

- [ ] **Step 7: Implement catalog service**

Create `apps/api/app/services/strategy_catalog.py`:

```python
import json
from pathlib import Path

from pydantic import BaseModel, Field


API_ROOT = Path(__file__).resolve().parents[2]
LEAN_WORKSPACE_ROOT = API_ROOT / "lean-workspace"
DEFAULT_CATALOG_PATH = LEAN_WORKSPACE_ROOT / "strategies.json"


class StrategyDefinition(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    language: str = Field(min_length=1)
    asset_class: str = Field(min_length=1)
    default_symbol: str = Field(min_length=1)
    resolution: str = Field(min_length=1)
    project_path: Path
    enabled: bool = True

    def public_payload(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "asset_class": self.asset_class,
            "default_symbol": self.default_symbol,
            "resolution": self.resolution,
            "enabled": self.enabled,
        }


def load_enabled_strategies(catalog_path: Path = DEFAULT_CATALOG_PATH) -> list[StrategyDefinition]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    strategies: list[StrategyDefinition] = []
    for item in payload.get("strategies", []):
        strategy = StrategyDefinition(**item)
        if strategy.enabled:
            if not strategy.project_path.is_absolute():
                strategy.project_path = catalog_path.parent / strategy.project_path
            strategies.append(strategy)
    return strategies


def get_strategy_by_id(strategy_id: str, catalog_path: Path = DEFAULT_CATALOG_PATH) -> StrategyDefinition:
    normalized = strategy_id.strip()
    for strategy in load_enabled_strategies(catalog_path=catalog_path):
        if strategy.id == normalized:
            return strategy
    raise ValueError(f"Unknown strategy_id: {normalized}")
```

- [ ] **Step 8: Run catalog tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest tests/test_strategy_catalog.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit catalog task**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab
git add .gitignore apps/api/lean-workspace/strategies.json apps/api/lean-workspace/MovingAverageCross/config.json apps/api/lean-workspace/MovingAverageCross/main.py apps/api/app/services/strategy_catalog.py apps/api/tests/test_strategy_catalog.py
git commit -m "feat(api): add lean strategy catalog"
```

---

### Task 2: LEAN Backtest Service and Result Parser

**Files:**
- Create: `apps/api/app/services/lean_backtest.py`
- Test: `apps/api/tests/test_lean_backtest_service.py`

- [ ] **Step 1: Write failing backtest service tests**

Create `apps/api/tests/test_lean_backtest_service.py`:

```python
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
```

- [ ] **Step 2: Run backtest service tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest tests/test_lean_backtest_service.py -v
```

Expected: FAIL because `app.services.lean_backtest` does not exist.

- [ ] **Step 3: Implement LEAN backtest service**

Create `apps/api/app/services/lean_backtest.py`:

```python
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


def _tail_lines(stdout: str | None, stderr: str | None, limit: int = 30) -> list[str]:
    lines = []
    for text in (stdout or "", stderr or ""):
        lines.extend(line.strip() for line in text.splitlines() if line.strip())
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
    value = raw.get(name) or raw.get(name.lower()) or raw.get(name.replace(" ", ""))
    return str(value) if value is not None else None


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
        time = item.get("x") or item.get("time") or item.get("Time")
        value = item.get("y") or item.get("value") or item.get("Value")
        if time is None or value is None:
            continue
        try:
            points.append(EquityPoint(time=str(time), value=float(value)))
        except (TypeError, ValueError):
            continue
    return points


def _save_latest(result: BacktestResult, runtime_root: Path) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    _latest_path(runtime_root).write_text(result.model_dump_json(indent=2), encoding="utf-8")


def read_latest_backtest(runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> BacktestResult | None:
    path = _latest_path(runtime_root)
    if not path.exists():
        return None
    return BacktestResult.model_validate_json(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run backtest service tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest tests/test_lean_backtest_service.py tests/test_strategy_catalog.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit service task**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab
git add apps/api/app/services/lean_backtest.py apps/api/tests/test_lean_backtest_service.py
git commit -m "feat(api): add lean backtest runner"
```

---

### Task 3: Strategy Lab API Routes

**Files:**
- Modify: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Add failing API route tests**

Append to `apps/api/tests/test_mvp_routes.py`:

```python
from app.services.lean_backtest import BacktestResult, BacktestStatistics
from app.services.strategy_catalog import StrategyDefinition


def test_mvp_strategy_lab_strategies_route_returns_catalog(monkeypatch):
    def fake_list_strategies():
        return [
            StrategyDefinition(
                id="moving_average_cross",
                name="MovingAverageCross",
                description="fixture strategy",
                language="Python",
                asset_class="US Equity",
                default_symbol="AAPL",
                resolution="Daily",
                project_path="MovingAverageCross",
                enabled=True,
            )
        ]

    monkeypatch.setattr(mvp, "load_enabled_strategies", fake_list_strategies)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/strategies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategies"][0]["id"] == "moving_average_cross"
    assert "project_path" not in payload["strategies"][0]


def test_mvp_strategy_lab_latest_backtest_route_returns_null_initially(monkeypatch):
    monkeypatch.setattr(mvp, "read_latest_backtest", lambda: None)
    client = TestClient(create_app())

    response = client.get("/api/mvp/strategy-lab/backtests/latest")

    assert response.status_code == 200
    assert response.json() == {"latest": None}


def test_mvp_strategy_lab_backtest_route_returns_structured_result(monkeypatch):
    result = BacktestResult(
        run_id="20260612T101500Z-moving_average_cross",
        strategy_id="moving_average_cross",
        status="success",
        started_at="2026-06-12T10:15:00Z",
        completed_at="2026-06-12T10:16:15Z",
        duration_seconds=75.0,
        message="Backtest completed.",
        statistics=BacktestStatistics(total_net_profit="12.34%", sharpe_ratio="0.72"),
        equity=[],
        logs=["TRACE:: Backtest completed"],
        output_directory="apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross",
    )

    def fake_run(strategy_id: str) -> BacktestResult:
        assert strategy_id == "moving_average_cross"
        return result

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "moving_average_cross"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["statistics"]["total_net_profit"] == "12.34%"


def test_mvp_strategy_lab_backtest_route_rejects_unknown_strategy(monkeypatch):
    def fake_run(strategy_id: str) -> BacktestResult:
        raise ValueError("Unknown strategy_id: missing")

    monkeypatch.setattr(mvp, "run_lean_backtest", fake_run)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/api/mvp/strategy-lab/backtests",
        json={"strategy_id": "missing"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run API route tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest tests/test_mvp_routes.py -v
```

Expected: FAIL because the new Strategy Lab endpoints do not exist and route imports are missing.

- [ ] **Step 3: Add imports and request body**

Modify the top of `apps/api/app/api/routes/mvp.py` so these imports exist:

```python
from fastapi import APIRouter, Depends, HTTPException, Path
```

Add service imports near the other service imports:

```python
from app.services.lean_backtest import read_latest_backtest, run_lean_backtest
from app.services.strategy_catalog import load_enabled_strategies
```

Add this request model after `ResearchBody`:

```python
class BacktestBody(BaseModel):
    strategy_id: str = Field(min_length=1)

    @field_validator("strategy_id")
    @classmethod
    def strip_strategy_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped
```

- [ ] **Step 4: Add Strategy Lab API routes**

Add these routes after `strategy_lab_status()` and before `_normalize_path_ticker()`:

```python
@router.get("/strategy-lab/strategies")
def strategy_lab_strategies() -> dict:
    return {"strategies": [strategy.public_payload() for strategy in load_enabled_strategies()]}


@router.post("/strategy-lab/backtests")
def strategy_lab_run_backtest(body: BacktestBody) -> dict:
    try:
        result = run_lean_backtest(body.strategy_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return result.model_dump()


@router.get("/strategy-lab/backtests/latest")
def strategy_lab_latest_backtest() -> dict:
    latest = read_latest_backtest()
    return {"latest": latest.model_dump() if latest is not None else None}
```

- [ ] **Step 5: Run backend route tests**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest tests/test_mvp_routes.py tests/test_lean_backtest_service.py tests/test_strategy_catalog.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit API route task**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab
git add apps/api/app/api/routes/mvp.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): expose lean strategy lab routes"
```

---

### Task 4: Frontend Strategy Lab API Client

**Files:**
- Modify: `apps/web/src/lib/client-api.ts`
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Add failing E2E targets**

Append these tests to `apps/web/tests/mvp.spec.ts`:

```ts
test("strategy lab can run a cataloged LEAN backtest", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: true,
        summary: "Docker and LEAN are ready for local backtest preparation.",
        tools: [
          { name: "Docker CLI", available: true, version: "Docker version 29.5.3", message: "Docker CLI is available." },
          { name: "LEAN CLI", available: true, version: "lean, version 1.0.200", message: "LEAN CLI is available." }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/strategies", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategies: [
          {
            id: "moving_average_cross",
            name: "MovingAverageCross",
            description: "AAPL daily moving average crossover sample for local LEAN validation.",
            language: "Python",
            asset_class: "US Equity",
            default_symbol: "AAPL",
            resolution: "Daily",
            enabled: true
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/latest", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { latest: null } });
  });
  await page.route("**/api/mvp/strategy-lab/backtests", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        run_id: "20260612T101500Z-moving_average_cross",
        strategy_id: "moving_average_cross",
        status: "success",
        started_at: "2026-06-12T10:15:00Z",
        completed_at: "2026-06-12T10:16:15Z",
        duration_seconds: 75,
        message: "Backtest completed.",
        statistics: {
          total_net_profit: "12.34%",
          compounding_annual_return: "8.10%",
          sharpe_ratio: "0.72",
          drawdown: "15.20%",
          win_rate: "48%",
          total_trades: "24"
        },
        equity: [{ time: "2020-01-01", value: 100000 }],
        logs: ["TRACE:: Backtest completed"],
        output_directory: "apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross"
      }
    });
  });

  await page.goto("/strategy-lab");
  await page.getByRole("button", { name: "运行回测" }).click();

  await expect(page.getByText("MovingAverageCross")).toBeVisible();
  await expect(page.getByText("Backtest completed.")).toBeVisible();
  await expect(page.getByText("12.34%")).toBeVisible();
  await expect(page.getByText("Sharpe")).toBeVisible();
  await expect(page.getByText("TRACE:: Backtest completed")).toBeVisible();
});

test("strategy lab displays LEAN backtest failures", async ({ page }) => {
  await page.route("**/api/mvp/strategy-lab/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        can_run_backtests: false,
        summary: "Strategy Lab is partially configured.",
        tools: [{ name: "LEAN CLI", available: false, version: null, message: "LEAN CLI is not installed or is not on PATH." }]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/strategies", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        strategies: [
          {
            id: "moving_average_cross",
            name: "MovingAverageCross",
            description: "AAPL daily moving average crossover sample for local LEAN validation.",
            language: "Python",
            asset_class: "US Equity",
            default_symbol: "AAPL",
            resolution: "Daily",
            enabled: true
          }
        ]
      }
    });
  });
  await page.route("**/api/mvp/strategy-lab/backtests/latest", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { latest: null } });
  });
  await page.route("**/api/mvp/strategy-lab/backtests", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        run_id: "20260612T101500Z-moving_average_cross",
        strategy_id: "moving_average_cross",
        status: "unavailable",
        started_at: "2026-06-12T10:15:00Z",
        completed_at: "2026-06-12T10:15:01Z",
        duration_seconds: 1,
        message: "Strategy Lab is partially configured.",
        statistics: {
          total_net_profit: null,
          compounding_annual_return: null,
          sharpe_ratio: null,
          drawdown: null,
          win_rate: null,
          total_trades: null
        },
        equity: [],
        logs: ["LEAN CLI is not installed or is not on PATH."],
        output_directory: "apps/api/.runtime/strategy-lab/backtests/20260612T101500Z-moving_average_cross"
      }
    });
  });

  await page.goto("/strategy-lab");
  await page.getByRole("button", { name: "运行回测" }).click();

  await expect(page.getByText("环境未就绪")).toBeVisible();
  await expect(page.getByText("LEAN CLI is not installed or is not on PATH.")).toBeVisible();
});
```

- [ ] **Step 2: Run E2E tests to verify RED**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\web
npx playwright test --grep "strategy lab can run a cataloged LEAN backtest|strategy lab displays LEAN backtest failures"
```

Expected: FAIL because the backtest panel and client helpers do not exist.

- [ ] **Step 3: Add frontend payload types and client helpers**

Append to `apps/web/src/lib/client-api.ts`:

```ts
export type StrategyDefinitionPayload = {
  id: string;
  name: string;
  description: string;
  language: string;
  asset_class: string;
  default_symbol: string;
  resolution: string;
  enabled: boolean;
};

export type StrategyListPayload = {
  strategies: StrategyDefinitionPayload[];
};

export type BacktestStatisticsPayload = {
  total_net_profit: string | null;
  compounding_annual_return: string | null;
  sharpe_ratio: string | null;
  drawdown: string | null;
  win_rate: string | null;
  total_trades: string | null;
};

export type EquityPointPayload = {
  time: string;
  value: number;
};

export type BacktestResultPayload = {
  run_id: string;
  strategy_id: string;
  status: "success" | "unavailable" | "failed" | "timeout" | "malformed_result";
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  message: string;
  statistics: BacktestStatisticsPayload;
  equity: EquityPointPayload[];
  logs: string[];
  output_directory: string;
};

export type LatestBacktestPayload = {
  latest: BacktestResultPayload | null;
};

const fallbackStrategies: StrategyListPayload = {
  strategies: [
    {
      id: "moving_average_cross",
      name: "MovingAverageCross",
      description: "AAPL daily moving average crossover sample for local LEAN validation.",
      language: "Python",
      asset_class: "US Equity",
      default_symbol: "AAPL",
      resolution: "Daily",
      enabled: true
    }
  ]
};

function fallbackBacktestResult(strategyId: string): BacktestResultPayload {
  const now = new Date().toISOString();
  return {
    run_id: `offline-${strategyId}`,
    strategy_id: strategyId,
    status: "unavailable",
    started_at: now,
    completed_at: now,
    duration_seconds: 0,
    message: "后端 API 暂不可用，无法运行 LEAN 回测。",
    statistics: {
      total_net_profit: null,
      compounding_annual_return: null,
      sharpe_ratio: null,
      drawdown: null,
      win_rate: null,
      total_trades: null
    },
    equity: [],
    logs: ["请确认后端 API、Docker 和 LEAN CLI 状态。"],
    output_directory: "local"
  };
}

function isStrategyDefinition(value: unknown): value is StrategyDefinitionPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.description === "string" &&
    typeof value.language === "string" &&
    typeof value.asset_class === "string" &&
    typeof value.default_symbol === "string" &&
    typeof value.resolution === "string" &&
    typeof value.enabled === "boolean"
  );
}

function isStrategyListPayload(value: unknown): value is StrategyListPayload {
  return isRecord(value) && Array.isArray(value.strategies) && value.strategies.every(isStrategyDefinition);
}

function isBacktestStatistics(value: unknown): value is BacktestStatisticsPayload {
  return (
    isRecord(value) &&
    (typeof value.total_net_profit === "string" || value.total_net_profit === null) &&
    (typeof value.compounding_annual_return === "string" || value.compounding_annual_return === null) &&
    (typeof value.sharpe_ratio === "string" || value.sharpe_ratio === null) &&
    (typeof value.drawdown === "string" || value.drawdown === null) &&
    (typeof value.win_rate === "string" || value.win_rate === null) &&
    (typeof value.total_trades === "string" || value.total_trades === null)
  );
}

function isEquityPoint(value: unknown): value is EquityPointPayload {
  return isRecord(value) && typeof value.time === "string" && typeof value.value === "number";
}

function isBacktestResultPayload(value: unknown): value is BacktestResultPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.strategy_id === "string" &&
    ["success", "unavailable", "failed", "timeout", "malformed_result"].includes(String(value.status)) &&
    typeof value.started_at === "string" &&
    typeof value.completed_at === "string" &&
    typeof value.duration_seconds === "number" &&
    typeof value.message === "string" &&
    isBacktestStatistics(value.statistics) &&
    Array.isArray(value.equity) &&
    value.equity.every(isEquityPoint) &&
    Array.isArray(value.logs) &&
    value.logs.every((item) => typeof item === "string") &&
    typeof value.output_directory === "string"
  );
}

function isLatestBacktestPayload(value: unknown): value is LatestBacktestPayload {
  return isRecord(value) && (value.latest === null || isBacktestResultPayload(value.latest));
}

export async function getStrategyCatalog(): Promise<StrategyListPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/strategies`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategies;
    }
    const payload: unknown = await response.json();
    return isStrategyListPayload(payload) ? payload : fallbackStrategies;
  } catch {
    return fallbackStrategies;
  }
}

export async function getLatestBacktest(): Promise<LatestBacktestPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests/latest`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return { latest: null };
    }
    const payload: unknown = await response.json();
    return isLatestBacktestPayload(payload) ? payload : { latest: null };
  } catch {
    return { latest: null };
  }
}

export async function runStrategyBacktest(strategyId: string): Promise<BacktestResultPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests`, {
      body: JSON.stringify({ strategy_id: strategyId }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return fallbackBacktestResult(strategyId);
    }
    const payload: unknown = await response.json();
    return isBacktestResultPayload(payload) ? payload : fallbackBacktestResult(strategyId);
  } catch {
    return fallbackBacktestResult(strategyId);
  }
}
```

- [ ] **Step 4: Run TypeScript check**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\web
npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit frontend client task**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab
git add apps/web/src/lib/client-api.ts apps/web/tests/mvp.spec.ts
git commit -m "test(web): cover strategy lab backtest flow"
```

---

### Task 5: Strategy Lab Backtest UI

**Files:**
- Create: `apps/web/src/components/strategy-backtest-panel.tsx`
- Modify: `apps/web/src/app/strategy-lab/page.tsx`
- Modify: `apps/web/src/app/styles.css`
- Modify: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Create backtest panel component**

Create `apps/web/src/components/strategy-backtest-panel.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getLatestBacktest,
  getStrategyCatalog,
  runStrategyBacktest,
  type BacktestResultPayload,
  type StrategyDefinitionPayload
} from "@/lib/client-api";

const statusLabel: Record<BacktestResultPayload["status"], string> = {
  failed: "LEAN 返回失败",
  malformed_result: "结果不可解析",
  success: "回测完成",
  timeout: "回测超时",
  unavailable: "环境未就绪"
};

function metricRows(result: BacktestResultPayload | null) {
  return [
    ["Total Net Profit", result?.statistics.total_net_profit ?? "不可用"],
    ["Annual Return", result?.statistics.compounding_annual_return ?? "不可用"],
    ["Sharpe", result?.statistics.sharpe_ratio ?? "不可用"],
    ["Drawdown", result?.statistics.drawdown ?? "不可用"],
    ["Win Rate", result?.statistics.win_rate ?? "不可用"],
    ["Trades", result?.statistics.total_trades ?? "不可用"]
  ];
}

export function StrategyBacktestPanel() {
  const [strategies, setStrategies] = useState<StrategyDefinitionPayload[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState("moving_average_cross");
  const [result, setResult] = useState<BacktestResultPayload | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    let active = true;
    getStrategyCatalog().then((payload) => {
      if (!active) {
        return;
      }
      setStrategies(payload.strategies);
      if (payload.strategies[0]) {
        setSelectedStrategyId(payload.strategies[0].id);
      }
    });
    getLatestBacktest().then((payload) => {
      if (active) {
        setResult(payload.latest);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.id === selectedStrategyId) ?? strategies[0],
    [selectedStrategyId, strategies]
  );

  async function handleRun() {
    if (!selectedStrategy) {
      return;
    }
    setIsRunning(true);
    const payload = await runStrategyBacktest(selectedStrategy.id);
    setResult(payload);
    setIsRunning(false);
  }

  return (
    <section className="data-panel backtest-panel" aria-label="LEAN 回测">
      <div className="panel-heading">
        <div>
          <h3>LEAN 回测</h3>
          <p>运行白名单内置策略，结果仅用于研究验证</p>
        </div>
        <button className="primary-action" type="button" disabled={isRunning || !selectedStrategy} onClick={handleRun}>
          {isRunning ? "运行中" : "运行回测"}
        </button>
      </div>

      <div className="strategy-grid">
        <div className="strategy-list" aria-label="策略列表">
          {strategies.map((strategy) => (
            <button
              className={strategy.id === selectedStrategyId ? "strategy-option active" : "strategy-option"}
              key={strategy.id}
              type="button"
              onClick={() => setSelectedStrategyId(strategy.id)}
            >
              <strong>{strategy.name}</strong>
              <span>{strategy.default_symbol} · {strategy.resolution} · {strategy.language}</span>
              <p>{strategy.description}</p>
            </button>
          ))}
        </div>

        <div className="backtest-result">
          <div className="result-toolbar">
            <div>
              <span className="market-label">最近一次回测</span>
              <strong>{result ? statusLabel[result.status] : "尚未运行回测"}</strong>
            </div>
            {result ? (
              <span className={result.status === "success" ? "status-pill success" : "status-pill warning"}>
                {result.status}
              </span>
            ) : (
              <span className="status-pill neutral">等待</span>
            )}
          </div>

          <p className="result-message">{result?.message ?? "选择策略后点击运行回测。"}</p>

          <div className="backtest-metrics">
            {metricRows(result).map(([label, value]) => (
              <article className="market-card" key={label}>
                <span className="market-label">{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>

          <div className="log-box" aria-label="回测日志">
            {(result?.logs.length ? result.logs : ["暂无回测日志"]).map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Render panel on Strategy Lab page**

Modify `apps/web/src/app/strategy-lab/page.tsx`:

```tsx
import { AppShell } from "@/components/app-shell";
import { StrategyBacktestPanel } from "@/components/strategy-backtest-panel";
import { StrategyLabStatusPanel } from "@/components/strategy-lab-status-panel";
import { sampleDashboard } from "@/lib/sample-data";

export default function StrategyLabPage() {
  return (
    <AppShell prompts={sampleDashboard.ai_prompts}>
      <div className="module-view">
        <header className="page-header">
          <div>
            <p>LEAN 回测预备环境与数据源就绪度</p>
            <h2>策略实验室</h2>
          </div>
          <div className="status-pill neutral">预备</div>
        </header>

        <StrategyLabStatusPanel />
        <StrategyBacktestPanel />
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 3: Add Strategy Lab styles**

Append to `apps/web/src/app/styles.css`:

```css
.primary-action {
  background: #182235;
  border: 1px solid #182235;
  border-radius: 7px;
  color: #ffffff;
  cursor: pointer;
  min-height: 36px;
  padding: 7px 12px;
}

.primary-action:disabled {
  cursor: wait;
  opacity: 0.68;
}

.strategy-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  padding: 16px;
}

.strategy-list {
  display: grid;
  gap: 10px;
}

.strategy-option {
  background: #ffffff;
  border: 1px solid #d9dee7;
  border-radius: 8px;
  color: #172033;
  cursor: pointer;
  display: grid;
  gap: 5px;
  padding: 12px;
  text-align: left;
}

.strategy-option.active {
  border-color: #182235;
  box-shadow: inset 3px 0 0 #182235;
}

.strategy-option strong,
.strategy-option p,
.strategy-option span,
.result-message,
.log-box p {
  margin: 0;
}

.strategy-option span,
.strategy-option p,
.result-message {
  color: #667085;
  font-size: 0.86rem;
}

.backtest-result {
  border: 1px solid #e5eaf0;
  border-radius: 8px;
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 14px;
}

.result-toolbar {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.result-toolbar strong {
  display: block;
  font-size: 1.15rem;
}

.backtest-metrics {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.log-box {
  background: #111827;
  border-radius: 8px;
  color: #dce5f2;
  display: grid;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 0.8rem;
  gap: 6px;
  max-height: 170px;
  overflow: auto;
  padding: 12px;
}

@media (max-width: 900px) {
  .strategy-grid,
  .backtest-metrics {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Run frontend checks**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\web
npm run lint
npx playwright test --grep "strategy lab renders readiness status|strategy lab can run a cataloged LEAN backtest|strategy lab displays LEAN backtest failures"
```

Expected: PASS.

- [ ] **Step 5: Commit UI task**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab
git add apps/web/src/components/strategy-backtest-panel.tsx apps/web/src/app/strategy-lab/page.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "feat(web): add lean backtest panel"
```

---

### Task 6: Final Verification

**Files:**
- Modify only files touched by earlier tasks if verification exposes a failure.

- [ ] **Step 1: Run backend full test suite**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\api
python -m pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 2: Run frontend type check**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\web
npm run lint
```

Expected: PASS.

- [ ] **Step 3: Run frontend production build**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\web
npm run build
```

Expected: PASS and route list still includes `/strategy-lab`, `/watchlist`, and `/settings`.

- [ ] **Step 4: Run Playwright E2E**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab\apps\web
npx playwright test
```

Expected: all Playwright tests PASS.

- [ ] **Step 5: Validate Compose config**

Run:

```powershell
cd D:\Documents\AI美股\.worktrees\codex-lean-strategy-lab
$dockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if (Test-Path $dockerBin) { $env:Path = "$dockerBin;$env:Path" }
docker compose config
```

Expected: command exits successfully and prints merged Compose config. If Docker CLI is unavailable, record the exact error; the app must still tolerate Docker and LEAN unavailable status.

- [ ] **Step 6: Browser verification**

With the app available at `http://127.0.0.1:3000`, verify:

- `/strategy-lab` shows `回测环境`.
- `/strategy-lab` shows `LEAN 回测`.
- `MovingAverageCross` appears in the strategy list.
- Clicking `运行回测` returns either a structured success result or a structured unavailable/failed result.
- `/settings` still shows `数据源状态`.
- `/watchlist` still shows `市场快照`.
- Dashboard and AI sidecar still render.

- [ ] **Step 7: Commit verification fixes if needed**

If code changed during verification:

```powershell
git add .gitignore apps/api/lean-workspace/strategies.json apps/api/lean-workspace/MovingAverageCross/config.json apps/api/lean-workspace/MovingAverageCross/main.py apps/api/app/services/strategy_catalog.py apps/api/app/services/lean_backtest.py apps/api/app/api/routes/mvp.py apps/api/tests/test_strategy_catalog.py apps/api/tests/test_lean_backtest_service.py apps/api/tests/test_mvp_routes.py apps/web/src/lib/client-api.ts apps/web/src/components/strategy-backtest-panel.tsx apps/web/src/app/strategy-lab/page.tsx apps/web/src/app/styles.css apps/web/tests/mvp.spec.ts
git commit -m "fix: stabilize lean strategy lab mvp"
```

If no code changed:

```powershell
git status --short
```

Expected: clean working tree.

---

## Self-Review

- Spec coverage: catalog, sample LEAN project, local `lean backtest`, readiness gating, result parsing, latest result, API routes, frontend panel, failure states, and tests are covered.
- Scope control: live trading, broker connections, cloud backtests, user code upload, strategy optimization, and AI-generated executable strategy code are excluded.
- Type consistency: backend `BacktestResult`, `BacktestStatistics`, and `EquityPoint` match frontend `BacktestResultPayload`, `BacktestStatisticsPayload`, and `EquityPointPayload`.
- TDD coverage: each implementation task starts with tests and has pass commands before commit.
