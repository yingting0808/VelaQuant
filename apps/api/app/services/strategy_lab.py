from pydantic import BaseModel


class StrategyToolStatus(BaseModel):
    name: str
    available: bool
    version: str | None
    message: str


class StrategyLabStatus(BaseModel):
    can_run_backtests: bool
    summary: str
    tools: list[StrategyToolStatus]


def get_strategy_lab_status() -> StrategyLabStatus:
    return StrategyLabStatus(
        can_run_backtests=False,
        summary="Strategy Lab readiness checks are not configured yet.",
        tools=[],
    )
