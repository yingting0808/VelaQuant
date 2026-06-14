from uuid import UUID

from sqlmodel import Session

from app.services.strategy_lifecycle import get_strategy_lifecycle
from app.services.strategy_registry import (
    DEFAULT_PAPER_STRATEGY_ID,
    DEFAULT_PAPER_STRATEGY_NAME,
    DEFAULT_PAPER_STRATEGY_NOTIONAL,
    DEFAULT_PAPER_STRATEGY_VERSION,
    StrategyExecutionBinding,
    StrategyExecutionMode,
    get_registered_strategy_execution_binding,
)


def get_strategy_execution_binding(
    session: Session,
    team_id: UUID,
    strategy_id: str,
    *,
    notional: float | None = None,
) -> StrategyExecutionBinding:
    normalized = _normalize_strategy_id(strategy_id)
    if normalized != DEFAULT_PAPER_STRATEGY_ID:
        raise ValueError(f"Strategy is not registered for execution: {normalized}")
    return get_registered_strategy_execution_binding(
        session,
        team_id,
        normalized,
        notional=notional,
    )


def assert_strategy_execution_allowed(
    session: Session,
    strategy_id: str,
    *,
    requested_mode: str,
) -> None:
    normalized_strategy_id = _normalize_strategy_id(strategy_id)
    if normalized_strategy_id != DEFAULT_PAPER_STRATEGY_ID:
        raise ValueError(f"Strategy is not registered for execution: {normalized_strategy_id}")

    lifecycle = get_strategy_lifecycle(session)
    if lifecycle.strategy_id != normalized_strategy_id:
        raise ValueError(f"Strategy is not registered for lifecycle control: {normalized_strategy_id}")

    if lifecycle.current_stage == "killed":
        raise ValueError(f"Strategy {normalized_strategy_id} is killed; execution is blocked.")

    if lifecycle.can_kill or lifecycle.recommended_stage == "killed":
        raise ValueError(f"Lifecycle marks strategy {normalized_strategy_id} for kill review; execution is blocked.")

    normalized_mode = _normalize_execution_mode(requested_mode)
    if normalized_mode == StrategyExecutionMode.live:
        raise ValueError("Live broker execution is disabled; no live approval or broker adapter is enabled.")

    allowed_modes = _allowed_modes_for_stage(lifecycle.current_stage)
    if normalized_mode not in allowed_modes:
        raise ValueError(
            f"Lifecycle does not allow execution mode {requested_mode} "
            f"for strategy {normalized_strategy_id} in stage {lifecycle.current_stage}."
        )


def _allowed_modes_for_stage(stage: str) -> set[StrategyExecutionMode]:
    if stage == "paper":
        return {StrategyExecutionMode.paper}
    if stage == "shadow_candidate":
        return {StrategyExecutionMode.paper}
    if stage == "shadow":
        return {StrategyExecutionMode.paper, StrategyExecutionMode.shadow}
    if stage == "live_small":
        return {StrategyExecutionMode.paper, StrategyExecutionMode.shadow, StrategyExecutionMode.live_small}
    if stage == "live":
        return {
            StrategyExecutionMode.paper,
            StrategyExecutionMode.shadow,
            StrategyExecutionMode.live_small,
            StrategyExecutionMode.live,
        }
    return set()


def _normalize_execution_mode(value: str) -> StrategyExecutionMode:
    normalized = value.strip().lower().replace("-", "_")
    try:
        return StrategyExecutionMode(normalized)
    except ValueError as error:
        raise ValueError(f"Unknown execution mode: {value}") from error


def _normalize_strategy_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("strategy_id must not be empty")
    return normalized

