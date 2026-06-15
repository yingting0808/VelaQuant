import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import StrategyActiveBinding, StrategyLifecycleState, StrategyVersionRecord
from app.services import strategy_control
from app.services.strategy_control import (
    StrategyExecutionBinding,
    StrategyExecutionMode,
    assert_strategy_execution_allowed,
    get_strategy_execution_binding,
)
from app.services.strategy_versions import activate_strategy_version, register_strategy_version
from app.services.workspace import get_or_create_default_workspace
from app.trading_core.events import EventSource, MarketEvent, MarketEventType, Sentiment
from app.trading_core.portfolio import PortfolioState


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_registered_paper_strategy_loads_execution_binding():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        binding = get_strategy_execution_binding(session, workspace.team.id, "deterministic_watchlist_v1")

        assert isinstance(binding, StrategyExecutionBinding)
        assert binding.strategy_id == "deterministic_watchlist_v1"
        assert binding.execution_mode == StrategyExecutionMode.paper
        assert binding.strategy_engine.strategy_id == "deterministic_watchlist_v1"
        assert not hasattr(binding, "strategy")
    assert binding.supports_live is False
    assert binding.supports_hot_swap is True


def test_moving_average_cross_loads_paper_runtime_binding():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        binding = get_strategy_execution_binding(session, workspace.team.id, "moving_average_cross", notional=900)
        result = binding.strategy_engine.generate_intents(
            MarketEvent(
                source=EventSource.market_data,
                event_type=MarketEventType.price_move,
                ticker="AAPL",
                occurred_at=datetime.now(timezone.utc),
                summary="AAPL fast average is above slow average.",
                sentiment=Sentiment.positive,
                confidence=0.88,
                impact_score=0.72,
                metadata={"fast_sma": 192.4, "slow_sma": 181.2},
            ),
            PortfolioState(cash=100000, equity=100000),
        )

        assert isinstance(binding, StrategyExecutionBinding)
        assert binding.strategy_id == "moving_average_cross"
        assert binding.execution_mode == StrategyExecutionMode.paper
        assert binding.strategy_engine.strategy_id == "moving_average_cross"
        assert binding.supports_live is False
        assert binding.supports_hot_swap is True
        assert result.intents[0].notional == 900


def test_execution_binding_uses_active_strategy_version_parameters():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        register_strategy_version(
            session,
            strategy_id="deterministic_watchlist_v1",
            version="v2",
            parameters_json='{"notional": 750}',
        )
        activate_strategy_version(
            session,
            strategy_id="deterministic_watchlist_v1",
            version="v2",
            reason="test hot swap",
        )

        binding = get_strategy_execution_binding(session, workspace.team.id, "deterministic_watchlist_v1")
        result = binding.strategy_engine.generate_intents(
            MarketEvent(
                source=EventSource.manual,
                event_type=MarketEventType.news,
                ticker="AAPL",
                occurred_at=datetime.now(timezone.utc),
                summary="positive version binding event",
                sentiment=Sentiment.positive,
                confidence=0.9,
                impact_score=0.8,
            ),
            PortfolioState(cash=100000, equity=100000),
        )

        assert binding.version == "v2"
        assert binding.supports_hot_swap is True
        assert result.intents[0].notional == 750


def test_strategy_control_delegates_execution_binding_to_registry(monkeypatch):
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        calls = []
        registry_binding = StrategyExecutionBinding(
            strategy_id="deterministic_watchlist_v1",
            name="Registry-bound Strategy",
            version="registry-version",
            execution_mode=StrategyExecutionMode.paper,
            strategy_engine="registry-engine",
            supports_live=False,
            supports_hot_swap=True,
        )

        def fake_registry_binding(session_arg, team_id_arg, strategy_id_arg, *, notional=None):
            calls.append((session_arg, team_id_arg, strategy_id_arg, notional))
            return registry_binding

        monkeypatch.setattr(
            strategy_control,
            "get_registered_strategy_execution_binding",
            fake_registry_binding,
            raising=False,
        )

        binding = get_strategy_execution_binding(
            session,
            workspace.team.id,
            "deterministic_watchlist_v1",
            notional=321,
        )

    assert binding is registry_binding
    assert calls == [(session, workspace.team.id, "deterministic_watchlist_v1", 321)]


def test_execution_binding_rejects_invalid_active_strategy_notional():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            StrategyVersionRecord(
                strategy_id="deterministic_watchlist_v1",
                version="broken",
                parameters_json='{"notional": -100}',
            )
        )
        session.add(
            StrategyActiveBinding(
                strategy_id="deterministic_watchlist_v1",
                active_version="broken",
                activation_reason="corrupt external write",
            )
        )
        session.commit()

        with pytest.raises(ValueError, match="Active strategy notional must be positive"):
            get_strategy_execution_binding(session, workspace.team.id, "deterministic_watchlist_v1")


def test_strategy_version_activation_rejects_invalid_executable_notional_before_binding_changes():
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


def test_unregistered_strategy_is_rejected():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        with pytest.raises(ValueError, match="Strategy is not registered for execution"):
            get_strategy_execution_binding(session, workspace.team.id, "missing_strategy")


def test_lifecycle_allows_paper_strategy_to_execute_in_paper_stage():
    with make_session() as session:
        assert_strategy_execution_allowed(session, "deterministic_watchlist_v1", requested_mode="paper")


def test_lifecycle_rejects_live_execution_when_strategy_is_in_paper_stage():
    with make_session() as session:
        with pytest.raises(ValueError, match="Live broker execution is disabled"):
            assert_strategy_execution_allowed(session, "deterministic_watchlist_v1", requested_mode="live")


def test_moving_average_cross_rejects_live_execution():
    with make_session() as session:
        with pytest.raises(ValueError, match="Live broker execution is disabled"):
            assert_strategy_execution_allowed(session, "moving_average_cross", requested_mode="live")


def test_live_broker_execution_is_disabled_even_if_lifecycle_stage_is_live():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="live"))
        session.commit()

        with pytest.raises(ValueError, match="Live broker execution is disabled"):
            assert_strategy_execution_allowed(session, "deterministic_watchlist_v1", requested_mode="live")


def test_killed_strategy_rejects_even_paper_execution_with_explicit_block_reason():
    with make_session() as session:
        session.add(StrategyLifecycleState(strategy_id="deterministic_watchlist_v1", current_stage="killed"))
        session.commit()

        with pytest.raises(ValueError, match="is killed; execution is blocked"):
            assert_strategy_execution_allowed(session, "deterministic_watchlist_v1", requested_mode="paper")
