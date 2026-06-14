from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import ShadowObservation
from app.services.shadow_observation_health import get_shadow_observation_health
from app.services.workspace import get_or_create_default_workspace


def test_shadow_observation_health_collects_until_sample_is_ready():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            observation(
                team_id=workspace.team.id,
                trading_day="2026-06-30",
                status="observing",
                event_chain_count=6,
                residual_risk_count=2,
            )
        )
        session.commit()

        result = get_shadow_observation_health(session, as_of_trading_day="2026-06-30")

        assert result.status == "collecting"
        assert result.sample_ready is False
        assert result.observation_count == 1
        assert result.consecutive_observing_count == 1
        assert result.average_would_route_order_count == 2
        assert result.warnings == ["sample_not_ready"]


def test_shadow_observation_health_marks_stable_after_clean_shadow_sample():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        for index in range(5):
            session.add(
                observation(
                    team_id=workspace.team.id,
                    trading_day=f"2026-07-0{index + 1}",
                    status="observing",
                    event_chain_count=6,
                    residual_risk_count=1,
                )
            )
        session.commit()

        result = get_shadow_observation_health(session, as_of_trading_day="2026-07-05")

        assert result.status == "stable"
        assert result.sample_ready is True
        assert result.observation_count == 5
        assert result.consecutive_observing_count == 5
        assert result.warnings == []


def test_shadow_observation_health_blocks_on_broken_event_chain():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            observation(
                team_id=workspace.team.id,
                trading_day="2026-07-01",
                status="observing",
                event_chain_count=0,
                residual_risk_count=1,
            )
        )
        session.commit()

        result = get_shadow_observation_health(session, as_of_trading_day="2026-07-01")

        assert result.status == "blocked"
        assert result.sample_ready is False
        assert "event_chain_missing" in result.warnings


def test_shadow_observation_health_ignores_future_observations_for_as_of_baseline():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        session.add(
            observation(
                team_id=workspace.team.id,
                trading_day="2026-06-13",
                status="observing",
                event_chain_count=6,
                residual_risk_count=1,
            )
        )
        for index in range(5):
            session.add(
                observation(
                    team_id=workspace.team.id,
                    trading_day=f"2026-06-{14 + index}",
                    status="observing",
                    event_chain_count=6,
                    residual_risk_count=1,
                )
            )
        session.commit()

        result = get_shadow_observation_health(session, as_of_trading_day="2026-06-13")

        assert result.status == "collecting"
        assert result.sample_ready is False
        assert result.observation_count == 1
        assert result.latest_trading_day == "2026-06-13"


def observation(
    *,
    team_id,
    trading_day: str,
    status: str,
    event_chain_count: int,
    residual_risk_count: int,
) -> ShadowObservation:
    return ShadowObservation(
        team_id=team_id,
        strategy_id="deterministic_watchlist_v1",
        trading_day=trading_day,
        status=status,
        can_request_shadow_review=status == "observing",
        observed_intent_count=6,
        would_route_order_count=2,
        event_chain_count=event_chain_count,
        residual_risk_count=residual_risk_count,
        blocked_reason=None if status == "observing" else "blocked",
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
