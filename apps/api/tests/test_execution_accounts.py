from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine

from app.services.execution_accounts import get_or_create_strategy_execution_accounts


def test_execution_accounts_create_isolated_shadow_and_live_small_accounts():
    with make_session() as session:
        team_id = uuid4()

        accounts = get_or_create_strategy_execution_accounts(
            session,
            team_id=team_id,
            strategy_id="deterministic_watchlist_v1",
        )

        assert [account.mode for account in accounts] == ["paper", "shadow", "live_small"]
        assert [account.strategy_id for account in accounts] == [
            "deterministic_watchlist_v1",
            "deterministic_watchlist_v1",
            "deterministic_watchlist_v1",
        ]
        assert accounts[0].cash == 100000.0
        assert accounts[1].cash == 100000.0
        assert accounts[2].cash == 5000.0


def test_execution_accounts_are_idempotent_per_strategy_and_mode():
    with make_session() as session:
        team_id = uuid4()

        first = get_or_create_strategy_execution_accounts(
            session,
            team_id=team_id,
            strategy_id="deterministic_watchlist_v1",
        )
        second = get_or_create_strategy_execution_accounts(
            session,
            team_id=team_id,
            strategy_id="deterministic_watchlist_v1",
        )

        assert [account.id for account in second] == [account.id for account in first]


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
