from subprocess import CompletedProcess, TimeoutExpired

from app.services.strategy_lab import get_strategy_lab_status


def successful_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    output = {
        ("docker", "--version"): "Docker version 29.5.3, build d1c06ef",
        ("docker", "compose", "version"): "Docker Compose version v5.1.4",
        ("docker", "info"): "Client:\n Version: 29.5.3\nServer:\n Containers: 0",
        ("docker", "image", "inspect", "quantconnect/lean:latest"): "quantconnect/lean:latest",
        ("lean", "--version"): "lean, version 1.0.200",
    }[tuple(command)]
    return CompletedProcess(command, 0, stdout=output, stderr="")


def missing_lean_image_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["docker", "image", "inspect", "quantconnect/lean:latest"]:
        return CompletedProcess(command, 1, stdout="", stderr="No such image: quantconnect/lean:latest")
    return successful_runner(command, timeout)


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


def permission_error_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["docker", "info"]:
        raise PermissionError("Access denied")
    return successful_runner(command, timeout)


def missing_all_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    raise FileNotFoundError(command[0])


def legacy_compose_runner(command: list[str], timeout: float) -> CompletedProcess[str]:
    if command == ["docker", "compose", "version"]:
        return CompletedProcess(command, 1, stdout="", stderr="docker: 'compose' is not a docker command")
    if command == ["docker-compose", "--version"]:
        return CompletedProcess(command, 0, stdout="docker-compose version 1.29.2", stderr="")
    return successful_runner(command, timeout)


def vectorbt_available(module_name: str) -> str | None:
    if module_name == "vectorbt":
        return "0.28.1"
    return None


def vectorbt_missing(module_name: str) -> str | None:
    return None


def test_strategy_lab_status_is_ready_when_all_tools_are_available():
    status = get_strategy_lab_status(
        command_runner=successful_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_available,
    )

    assert status.can_run_backtests is True
    assert status.summary == "Docker and LEAN are ready for local backtest preparation."
    assert {tool.name for tool in status.tools} == {
        "Docker CLI",
        "Docker Compose",
        "Docker engine",
        "LEAN Docker image",
        "LEAN CLI",
        "vectorbt",
    }


def test_strategy_lab_status_requires_cached_lean_engine_image_for_lean_backtests():
    status = get_strategy_lab_status(
        command_runner=missing_lean_image_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_available,
    )

    assert status.can_run_backtests is False
    assert status.summary == "QuantConnect LEAN engine image is not cached; real LEAN backtests are unavailable."
    image = next(tool for tool in status.tools if tool.name == "LEAN Docker image")
    assert image.available is False
    assert "docker pull quantconnect/lean:latest" in image.message


def test_strategy_lab_status_keeps_backtests_available_when_vectorbt_is_ready_without_lean():
    status = get_strategy_lab_status(
        command_runner=missing_lean_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_available,
    )

    assert status.can_run_backtests is False
    lean = next(tool for tool in status.tools if tool.name == "LEAN CLI")
    vectorbt = next(tool for tool in status.tools if tool.name == "vectorbt")
    assert lean.available is False
    assert "not installed" in lean.message
    assert vectorbt.available is True
    assert status.summary == "vectorbt research fallback is ready, but real LEAN backtests are unavailable."


def test_strategy_lab_status_keeps_backtests_available_when_only_vectorbt_is_ready():
    status = get_strategy_lab_status(
        command_runner=missing_all_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_available,
    )

    assert status.can_run_backtests is False
    assert next(tool for tool in status.tools if tool.name == "vectorbt").available is True
    assert next(tool for tool in status.tools if tool.name == "Docker CLI").available is False


def test_strategy_lab_status_accepts_legacy_docker_compose_binary():
    status = get_strategy_lab_status(
        command_runner=legacy_compose_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_available,
    )

    compose = next(tool for tool in status.tools if tool.name == "Docker Compose")
    assert compose.available is True
    assert compose.version == "docker-compose version 1.29.2"


def test_strategy_lab_status_reports_docker_engine_timeout():
    status = get_strategy_lab_status(
        command_runner=timeout_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_missing,
    )

    assert status.can_run_backtests is False
    engine = next(tool for tool in status.tools if tool.name == "Docker engine")
    assert engine.available is False
    assert "timed out" in engine.message


def test_strategy_lab_status_reports_docker_engine_nonzero_exit():
    status = get_strategy_lab_status(
        command_runner=docker_engine_error_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_missing,
    )

    assert status.can_run_backtests is False
    engine = next(tool for tool in status.tools if tool.name == "Docker engine")
    assert engine.available is False
    assert "Docker daemon unavailable" in engine.message


def test_strategy_lab_status_reports_docker_engine_os_error():
    status = get_strategy_lab_status(
        command_runner=permission_error_runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_missing,
    )

    assert status.can_run_backtests is False
    engine = next(tool for tool in status.tools if tool.name == "Docker engine")
    assert engine.available is False
    assert "Access denied" in engine.message


def test_strategy_lab_status_prioritizes_missing_lean_engine_image_over_cli_timeout():
    def runner(command: list[str], timeout: float) -> CompletedProcess[str]:
        if command == ["docker", "image", "inspect", "quantconnect/lean:latest"]:
            return CompletedProcess(command, 1, stdout="", stderr="No such image: quantconnect/lean:latest")
        if command == ["lean", "--version"]:
            raise TimeoutExpired(command, timeout)
        return successful_runner(command, timeout)

    status = get_strategy_lab_status(
        command_runner=runner,
        timeout_seconds=1.0,
        module_version_checker=vectorbt_available,
    )

    assert status.can_run_backtests is False
    assert status.summary == "QuantConnect LEAN engine image is not cached; real LEAN backtests are unavailable."
