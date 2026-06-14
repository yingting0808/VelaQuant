from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import PaperOrder, PaperReview, ShadowObservation
from app.services.event_ledger import EventLedgerReplay, EventLedgerReplayChain, EventLedgerStatus, EventLedgerTopicCount
from app.services import shadow_observation
from app.services.shadow_observation import _latest_trading_day, record_shadow_observation_from_packet
from app.services.shadow_review import ShadowReviewChecklistItem, ShadowReviewPayload, ShadowReviewResidualRisk
from app.services.workspace import get_or_create_default_workspace


def test_shadow_observation_records_ready_state_without_creating_orders():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        result = record_shadow_observation_from_packet(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-30",
            current_stage="shadow",
            shadow_review=ready_packet(),
            event_ledger=event_ledger(),
        )

        assert result.status == "observing"
        assert result.can_request_shadow_review is True
        assert result.observed_intent_count == 6
        assert result.would_route_order_count == 6
        assert result.blocked_reason is None
        assert session.exec(select(PaperOrder)).all() == []
        assert len(session.exec(select(ShadowObservation)).all()) == 1


def test_shadow_observation_is_idempotent_per_strategy_and_trading_day():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        first = record_shadow_observation_from_packet(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-30",
            current_stage="shadow",
            shadow_review=ready_packet(),
            event_ledger=event_ledger(),
        )
        second = record_shadow_observation_from_packet(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-30",
            current_stage="shadow",
            shadow_review=ready_packet(),
            event_ledger=event_ledger(),
        )

        assert second.id == first.id
        assert len(session.exec(select(ShadowObservation)).all()) == 1


def test_shadow_observation_records_blocked_state_when_review_is_not_ready():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        blocked_packet = ready_packet().model_copy(
            update={
                "status": "blocked",
                "can_request_shadow_review": False,
                "recommended_stage": "paper",
                "summary": "blocked",
            }
        )

        result = record_shadow_observation_from_packet(
            session,
            team_id=workspace.team.id,
            trading_day="2026-06-30",
            current_stage="shadow",
            shadow_review=blocked_packet,
            event_ledger=event_ledger(),
        )

        assert result.status == "blocked"
        assert result.can_request_shadow_review is False
        assert result.blocked_reason == "blocked"


def test_shadow_observation_rejects_recording_before_shadow_stage():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        try:
            record_shadow_observation_from_packet(
                session,
                team_id=workspace.team.id,
                trading_day="2026-06-30",
                current_stage="paper",
                shadow_review=ready_packet(),
                event_ledger=event_ledger(),
            )
        except ValueError as error:
            assert "requires current lifecycle stage shadow" in str(error)
        else:
            raise AssertionError("Expected shadow observation to require shadow stage")

        assert session.exec(select(ShadowObservation)).all() == []


def test_shadow_latest_trading_day_ignores_future_simulation_reviews():
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)
        account_id = uuid4()
        session.add(
            PaperReview(
                account_id=account_id,
                team_id=workspace.team.id,
                trading_day="2026-06-13",
                equity=100000,
                cash=100000,
                realized_pnl=0,
                unrealized_pnl=0,
                trade_count=0,
                win_rate=0,
                average_win=0,
                average_loss=0,
                expectancy=0,
                notes="today",
            )
        )
        session.add(
            PaperReview(
                account_id=account_id,
                team_id=workspace.team.id,
                trading_day="2026-06-30",
                equity=110000,
                cash=100000,
                realized_pnl=1000,
                unrealized_pnl=500,
                trade_count=10,
                win_rate=0.8,
                average_win=80,
                average_loss=10,
                expectancy=49.8,
                notes="future simulation",
            )
        )
        session.commit()

        assert _latest_trading_day(session, workspace.team.id, as_of_trading_day="2026-06-13") == "2026-06-13"


def test_shadow_latest_trading_day_falls_back_to_market_trading_day(monkeypatch):
    monkeypatch.setattr(shadow_observation, "current_market_trading_day", lambda: "2026-06-12")
    with make_session() as session:
        workspace = get_or_create_default_workspace(session)

        assert _latest_trading_day(session, workspace.team.id) == "2026-06-12"


def ready_packet() -> ShadowReviewPayload:
    return ShadowReviewPayload(
        status="ready_for_manual_review",
        strategy_id="deterministic_watchlist_v1",
        can_request_shadow_review=True,
        recommended_stage="shadow",
        auto_promotion_enabled=False,
        checklist=[
            ShadowReviewChecklistItem(
                code="alpha_gates_passed",
                label="Alpha 门禁通过",
                passed=True,
                evidence=["8/8"],
            )
        ],
        residual_risks=[
            ShadowReviewResidualRisk(
                code="paper_to_shadow_gap",
                severity="info",
                detail="paper to shadow gap",
                evidence=["auto_promotion_enabled=false"],
            )
        ],
        summary="ready",
    )


def event_ledger() -> EventLedgerStatus:
    return EventLedgerStatus(
        total_event_count=680,
        latest_run_id=None,
        latest_run_status="completed",
        latest_run_event_count=30,
        latest_topic_counts=[EventLedgerTopicCount(topic="trade_intent", count=6)],
        latest_correlation_count=6,
        replay_ready=True,
        warnings=[],
        summary="ledger ready",
        latest_replay=EventLedgerReplay(
            run_id="00000000-0000-0000-0000-000000000001",
            event_count=30,
            chain_count=6,
            chains=[
                EventLedgerReplayChain(
                    correlation_id=f"chain-{index}",
                    ticker="AAPL",
                    topics=["market_event", "strategy_input", "trade_intent", "risk_decision", "order_state"],
                    order_states=["new", "validated", "risk_approved", "sent", "filled"],
                    terminal_state="filled",
                    event_count=5,
                )
                for index in range(6)
            ],
        ),
    )


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
