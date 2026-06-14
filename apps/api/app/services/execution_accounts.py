from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import PaperAccount, PaperTradingMode, utc_now


class StrategyExecutionAccountPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    team_id: UUID
    strategy_id: str
    name: str
    mode: str
    starting_cash: float
    cash: float
    realized_pnl: float


def get_or_create_strategy_execution_accounts(
    session: Session,
    *,
    team_id: UUID,
    strategy_id: str,
) -> list[StrategyExecutionAccountPayload]:
    normalized_strategy_id = _normalize_strategy_id(strategy_id)
    accounts = [
        _get_or_create_account(
            session,
            team_id=team_id,
            strategy_id=normalized_strategy_id,
            mode=PaperTradingMode.paper,
            name=f"{normalized_strategy_id} paper account",
            starting_cash=100000.0,
        ),
        _get_or_create_account(
            session,
            team_id=team_id,
            strategy_id=normalized_strategy_id,
            mode=PaperTradingMode.shadow,
            name=f"{normalized_strategy_id} shadow account",
            starting_cash=100000.0,
        ),
        _get_or_create_account(
            session,
            team_id=team_id,
            strategy_id=normalized_strategy_id,
            mode=PaperTradingMode.live_small,
            name=f"{normalized_strategy_id} live-small account",
            starting_cash=5000.0,
        ),
    ]
    return [_payload(account) for account in accounts]


def _get_or_create_account(
    session: Session,
    *,
    team_id: UUID,
    strategy_id: str,
    mode: PaperTradingMode,
    name: str,
    starting_cash: float,
) -> PaperAccount:
    account = session.exec(
        select(PaperAccount).where(
            PaperAccount.team_id == team_id,
            PaperAccount.strategy_id == strategy_id,
            PaperAccount.mode == mode,
        )
    ).first()
    if account is not None:
        return account

    account = PaperAccount(
        team_id=team_id,
        strategy_id=strategy_id,
        name=name,
        mode=mode,
        starting_cash=starting_cash,
        cash=starting_cash,
        updated_at=utc_now(),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _payload(account: PaperAccount) -> StrategyExecutionAccountPayload:
    return StrategyExecutionAccountPayload(
        id=account.id,
        team_id=account.team_id,
        strategy_id=account.strategy_id,
        name=account.name,
        mode=account.mode.value,
        starting_cash=account.starting_cash,
        cash=account.cash,
        realized_pnl=account.realized_pnl,
    )


def _normalize_strategy_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("strategy_id must not be empty")
    return normalized
