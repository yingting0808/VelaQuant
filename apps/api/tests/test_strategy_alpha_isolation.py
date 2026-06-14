from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import CoreEventLog, PaperAccount, PaperOrder, PaperOrderSide, PaperOrderStatus, Team
from app.services.strategy_alpha_isolation import get_strategy_alpha_isolation


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_strategy_alpha_isolation_reports_manual_override_without_counting_it_as_alpha_chain():
    with make_session() as session:
        team, account = _team_account(session)
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=team.id,
                strategy_id="deterministic_watchlist_v1:manual_override",
                ticker="AAPL",
                side=PaperOrderSide.buy,
                quantity=1,
                status=PaperOrderStatus.filled,
                fill_price=100,
                submitted_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        _event(
            session,
            team.id,
            "market_event",
            "manual-corr",
            '{"ticker":"AAPL","metadata":{"order_strategy_id":"deterministic_watchlist_v1:manual_override"}}',
        )
        _event(session, team.id, "trade_intent", "manual-corr", "{}")
        session.commit()

        payload = get_strategy_alpha_isolation(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert payload.isolated is True
        assert payload.strategy_order_count == 0
        assert payload.manual_override_order_count == 1
        assert payload.manual_override_event_chain_count == 1
        assert payload.filtered_event_chain_count == 0


def test_strategy_alpha_isolation_counts_registered_strategy_chains():
    with make_session() as session:
        team, account = _team_account(session)
        session.add(
            PaperOrder(
                account_id=account.id,
                team_id=team.id,
                strategy_id="deterministic_watchlist_v1",
                ticker="AAPL",
                side=PaperOrderSide.buy,
                quantity=1,
                status=PaperOrderStatus.filled,
                fill_price=100,
                submitted_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        _event(
            session,
            team.id,
            "market_event",
            "strategy-corr",
            '{"ticker":"AAPL","metadata":{"order_strategy_id":"deterministic_watchlist_v1"}}',
        )
        _event(session, team.id, "trade_intent", "strategy-corr", "{}")
        session.commit()

        payload = get_strategy_alpha_isolation(session, team_id=team.id, as_of_trading_day="2026-06-13")

        assert payload.isolated is True
        assert payload.strategy_order_count == 1
        assert payload.manual_override_order_count == 0
        assert payload.manual_override_event_chain_count == 0
        assert payload.filtered_event_chain_count == 1


def _team_account(session: Session) -> tuple[Team, PaperAccount]:
    team = Team(name="Alpha Isolation")
    session.add(team)
    session.commit()
    session.refresh(team)
    account = PaperAccount(team_id=team.id, name="paper")
    session.add(account)
    session.commit()
    session.refresh(account)
    return team, account


def _event(session: Session, team_id, topic: str, correlation_id: str, payload_json: str) -> CoreEventLog:
    event = CoreEventLog(
        team_id=team_id,
        event_id=f"{correlation_id}-{topic}-{uuid4()}",
        topic=topic,
        sequence=1,
        correlation_id=correlation_id,
        payload_json=payload_json,
        published_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
    )
    session.add(event)
    return event
