from subprocess import CompletedProcess, TimeoutExpired

from app.services.strategy_lab import get_strategy_lab_status


def successful_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    output = {
        ("docker", "--version"): "Docker version 29.5.3, build d1c06ef",
        ("docker", "compose", "version"): "Docker Compose version v5.1.4",
        ("docker", "info"): "Client:\n Version: 29.5.3\nServer:\n Containers: 0",
        ("lean", "--version"): "lean, version 1.0.200",
    }[tuple(command)]
    return CompletedProcess(command, 0, stdout=output, stderr="")


def missing_lean_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["lean", "--version"]:
        raise FileNotFoundError("lean")
    return successful_runner(command, timeout)


def timeout_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["docker", "info"]:
        raise TimeoutExpired(command, timeout)
    return successful_runner(command, timeout)


def docker_engine_error_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["docker", "info"]:
        return CompletedProcess(command, 1, stdout="", stderr="Docker daemon unavailable")
    return successful_runner(command, timeout)


def test_strategy_lab_status_is_ready_when_all_tools_are_available():
    status = get_strategy_lab_status(command_runner=successful_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is True
    assert status.summary == "Docker and LEAN are ready for local backtest preparation."
    assert {tool.name for tool in status.tools} == {"Docker CLI", "Docker Compose", "Docker engine", "LEAN CLI"}


def test_strategy_lab_status_reports_missing_lean_cli():
    status = get_strategy_lab_status(command_runner=missing_lean_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is False
    lean = next(tool for tool in status.tools if tool.name == "LEAN CLI")
    assert lean.available is False
    assert "not installed" in lean.message


def test_strategy_lab_status_reports_docker_engine_timeout():
    status = get_strategy_lab_status(command_runner=timeout_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is False
    engine = next(tool for tool in status.tools if tool.name == "Docker engine")
    assert engine.available is False
    assert "timed out" in engine.message


def test_strategy_lab_status_reports_docker_engine_nonzero_exit():
    status = get_strategy_lab_status(command_runner=docker_engine_error_runner, timeout_seconds=1.0)

    assert status.can_run_backtests is False
    engine = next(tool for tool in status.tools if tool.name == "Docker engine")
    assert engine.available is False
    assert "Docker daemon unavailable" in engine.message
