from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import ShadowObservation
from app.services.shadow_validation import get_shadow_validation
from app.services.workspace import get_or_create_default_workspace


def test_shadow_validation_collects_until_minimum_observation_sample():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            ShadowObservation(
                team_id=workspace.team.id,
                strategy_id="deterministic_watchlist_v1",
                trading_day="2026-06-30",
                status="observing",
                can_request_shadow_review=True,
                observed_intent_count=6,
                would_route_order_count=2,
                event_chain_count=6,
                residual_risk_count=2,
            )
        )
        session.commit()

        result = get_shadow_validation(session, as_of_trading_day="2026-06-30")

        assert result.shadow_ready is False
        assert result.status == "collecting"
        assert result.observation_count == 1
        assert result.remaining_observations == 4
        assert result.blockers == ["shadow_observation_sample"]


def test_shadow_validation_passes_after_stable_observation_sample():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        for index in range(5):
            session.add(
                ShadowObservation(
                    team_id=workspace.team.id,
                    strategy_id="deterministic_watchlist_v1",
                    trading_day=f"2026-07-0{index + 1}",
                    status="observing",
                    can_request_shadow_review=True,
                    observed_intent_count=6,
                    would_route_order_count=2,
                    event_chain_count=6,
                    residual_risk_count=1,
                )
            )
        session.commit()

        result = get_shadow_validation(session, as_of_trading_day="2026-07-05")

        assert result.shadow_ready is True
        assert result.status == "shadow_validated"
        assert result.observation_count == 5
        assert result.remaining_observations == 0
        assert result.blockers == []


def test_shadow_validation_blocks_on_blocked_observation():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            ShadowObservation(
                team_id=workspace.team.id,
                strategy_id="deterministic_watchlist_v1",
                trading_day="2026-06-30",
                status="blocked",
                can_request_shadow_review=False,
                observed_intent_count=0,
                would_route_order_count=0,
                event_chain_count=0,
                residual_risk_count=1,
                blocked_reason="blocked",
            )
        )
        session.commit()

        result = get_shadow_validation(session, as_of_trading_day="2026-06-30")

        assert result.shadow_ready is False
        assert result.status == "blocked"
        assert result.blockers == ["shadow_observation_blocked", "shadow_observation_sample"]


def test_shadow_validation_ignores_future_observations_for_as_of_baseline():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            ShadowObservation(
                team_id=workspace.team.id,
                strategy_id="deterministic_watchlist_v1",
                trading_day="2026-06-13",
                status="observing",
                can_request_shadow_review=True,
                observed_intent_count=6,
                would_route_order_count=2,
                event_chain_count=6,
                residual_risk_count=1,
            )
        )
        for index in range(5):
            session.add(
                ShadowObservation(
                    team_id=workspace.team.id,
                    strategy_id="deterministic_watchlist_v1",
                    trading_day=f"2026-06-{14 + index}",
                    status="observing",
                    can_request_shadow_review=True,
                    observed_intent_count=6,
                    would_route_order_count=2,
                    event_chain_count=6,
                    residual_risk_count=1,
                )
            )
        session.commit()

        result = get_shadow_validation(session, as_of_trading_day="2026-06-13")

        assert result.shadow_ready is False
        assert result.observation_count == 1
        assert result.latest_trading_day == "2026-06-13"
        assert result.remaining_observations == 4


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
