import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.strategy_versions import (
    activate_strategy_version,
    get_strategy_version_control,
    register_strategy_version,
    rollback_strategy_version,
)


def test_strategy_version_registry_seeds_default_active_version():
    with make_session() as session:
        state = get_strategy_version_control(session)

        assert state.active_strategy_id == "deterministic_watchlist_v1"
        assert state.active_version == "v1"
        assert len(state.versions) == 1
        assert state.versions[0].strategy_id == "deterministic_watchlist_v1"
        assert state.versions[0].version == "v1"
        assert state.versions[0].is_active is True


def test_strategy_version_control_can_hot_swap_and_rollback():
    with make_session() as session:
        register_strategy_version(
            session,
            strategy_id="deterministic_watchlist_v1",
            version="v2",
            parameters_json='{"notional": 1000}',
        )

        activate_strategy_version(
            session,
            strategy_id="deterministic_watchlist_v1",
            version="v2",
            reason="test hot swap",
        )

        assert get_strategy_version_control(session).active_version == "v2"

        rollback_strategy_version(session, strategy_id="deterministic_watchlist_v1")

        state = get_strategy_version_control(session)
        assert state.active_version == "v1"
        assert [item.version for item in state.versions] == ["v1", "v2"]
        assert [item.is_active for item in state.versions] == [True, False]


def test_strategy_version_activation_rejects_invalid_executable_parameters():
    with make_session() as session:
        register_strategy_version(
            session,
            strategy_id="deterministic_watchlist_v1",
            version="broken",
            parameters_json='{"notional": -100}',
        )

        with pytest.raises(ValueError, match="Active strategy notional must be positive"):
            activate_strategy_version(
                session,
                strategy_id="deterministic_watchlist_v1",
                version="broken",
                reason="test invalid hot swap",
            )

        assert get_strategy_version_control(session).active_version == "v1"


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
