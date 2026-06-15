import subprocess
from collections.abc import Callable
from importlib import metadata
from subprocess import CompletedProcess, TimeoutExpired

from app.core.config import get_settings
from pydantic import BaseModel


CommandRunner = Callable[[list[str], float], CompletedProcess[str]]
ModuleVersionChecker = Callable[[str], str | None]
LEAN_ENGINE_IMAGE = "quantconnect/lean:latest"


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


def default_module_version_checker(module_name: str) -> str | None:
    try:
        return metadata.version(module_name)
    except metadata.PackageNotFoundError:
        return None


def get_strategy_lab_status(
    *,
    command_runner: CommandRunner = default_command_runner,
    module_version_checker: ModuleVersionChecker = default_module_version_checker,
    timeout_seconds: float | None = None,
) -> StrategyLabStatus:
    settings = get_settings()
    timeout = timeout_seconds if timeout_seconds is not None else settings.strategy_command_timeout_seconds
    tools = [
        _check_tool("Docker CLI", ["docker", "--version"], command_runner, timeout),
        _check_any_tool(
            "Docker Compose",
            [["docker", "compose", "version"], ["docker-compose", "--version"]],
            command_runner,
            timeout,
        ),
        _check_tool("Docker engine", ["docker", "info"], command_runner, timeout),
        _check_lean_engine_image(command_runner, timeout),
        _check_tool("LEAN CLI", ["lean", "--version"], command_runner, timeout),
        _check_python_module("vectorbt", "vectorbt", module_version_checker),
    ]
    lean_ready = all(tool.available for tool in tools if tool.name != "vectorbt")
    vectorbt_ready = next(tool.available for tool in tools if tool.name == "vectorbt")
    ready = lean_ready
    summary = (
        "Docker and LEAN are ready for local backtest preparation."
        if lean_ready
        else "QuantConnect LEAN engine image is not cached; real LEAN backtests are unavailable."
        if _lean_image_missing(tools)
        else "vectorbt research fallback is ready, but real LEAN backtests are unavailable."
        if vectorbt_ready
        else "Strategy Lab is partially configured; review unavailable tools before running LEAN backtests."
    )
    return StrategyLabStatus(can_run_backtests=ready, summary=summary, tools=tools)


def _lean_cli_available(tools: list[StrategyToolStatus]) -> bool:
    return any(tool.name == "LEAN CLI" and tool.available for tool in tools)


def _lean_image_missing(tools: list[StrategyToolStatus]) -> bool:
    return any(tool.name == "LEAN Docker image" and not tool.available for tool in tools)


def _check_lean_engine_image(command_runner: CommandRunner, timeout: float) -> StrategyToolStatus:
    result = _check_tool(
        "LEAN Docker image",
        ["docker", "image", "inspect", LEAN_ENGINE_IMAGE],
        command_runner,
        timeout,
    )
    if result.available:
        return StrategyToolStatus(
            name=result.name,
            available=True,
            version=LEAN_ENGINE_IMAGE,
            message=f"{LEAN_ENGINE_IMAGE} is cached locally.",
        )
    return StrategyToolStatus(
        name=result.name,
        available=False,
        version=None,
        message=(
            f"{LEAN_ENGINE_IMAGE} is not cached locally; run "
            f"`docker pull {LEAN_ENGINE_IMAGE}` before real LEAN backtests."
        ),
    )


def _check_any_tool(
    name: str,
    commands: list[list[str]],
    command_runner: CommandRunner,
    timeout: float,
) -> StrategyToolStatus:
    failures: list[str] = []
    for command in commands:
        result = _check_tool(name, command, command_runner, timeout)
        if result.available:
            return result
        failures.append(result.message)
    return StrategyToolStatus(
        name=name,
        available=False,
        version=None,
        message=failures[0] if failures else f"{name} is not installed or is not on PATH.",
    )


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
    except OSError as error:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=f"{name} could not be checked: {error}.",
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


def _check_python_module(
    name: str,
    module_name: str,
    module_version_checker: ModuleVersionChecker,
) -> StrategyToolStatus:
    version = module_version_checker(module_name)
    if version is None:
        return StrategyToolStatus(
            name=name,
            available=False,
            version=None,
            message=f"{name} is not installed in the API runtime.",
        )

    return StrategyToolStatus(
        name=name,
        available=True,
        version=version,
        message=f"{name} is available in the API runtime.",
    )
