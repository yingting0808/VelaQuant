import subprocess
from collections.abc import Callable
from subprocess import CompletedProcess, TimeoutExpired

from app.core.config import get_settings
from pydantic import BaseModel


CommandRunner = Callable[[list[str], float], CompletedProcess[str]]


class StrategyToolStatus(BaseModel):
    name: str
    available: bool
    version: str | None
    message: str


class StrategyLabStatus(BaseModel):
    can_run_backtests: bool
    summary: str
    tools: list[StrategyToolStatus]


def default_command_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        shell=False,
        text=True,
        timeout=timeout,
    )


def get_strategy_lab_status(
    *,
    command_runner: CommandRunner = default_command_runner,
    timeout_seconds: float | None = None,
) -> StrategyLabStatus:
    settings = get_settings()
    timeout = timeout_seconds if timeout_seconds is not None else settings.strategy_command_timeout_seconds
    tools = [
        _check_tool("Docker CLI", ["docker", "--version"], command_runner, timeout),
        _check_tool("Docker Compose", ["docker", "compose", "version"], command_runner, timeout),
        _check_tool("Docker engine", ["docker", "info"], command_runner, timeout),
        _check_tool("LEAN CLI", ["lean", "--version"], command_runner, timeout),
    ]
    ready = all(tool.available for tool in tools)
    summary = (
        "Docker and LEAN are ready for local backtest preparation."
        if ready
        else "Strategy Lab is partially configured; review unavailable tools before running LEAN backtests."
    )
    return StrategyLabStatus(can_run_backtests=ready, summary=summary, tools=tools)


def _check_tool(
    name: str,
    command: list[str],
    command_runner: CommandRunner,
    timeout: float,
) -> StrategyToolStatus:
    try:
        completed = command_runner(command, timeout)
    except FileNotFoundError:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=f"{name} is not installed or is not on PATH.",
        )
    except TimeoutExpired:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=f"{name} check timed out after {timeout:.1f}s.",
        )

    output = (completed.stdout or completed.stderr or "").strip()
    first_line = output.splitlines()[0] if output else ""
    if completed.returncode != 0:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=first_line or f"{name} returned exit code {completed.returncode}.",
        )

    return StrategyToolStatus(
        name=name,
        available=True,
        version=first_line or "available",
        message=f"{name} is available.",
    )
