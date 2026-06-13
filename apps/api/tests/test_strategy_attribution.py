import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import (
    CoreEventLog,
    PaperAccount,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPosition,
    PaperReadiness,
    PaperReview,
)
from app.services.strategy_attribution import attribute_current_paper_strategy
from app.services.workspace import get_or_create_default_workspace


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _account(session: Session) -> PaperAccount:
    workspace = get_or_create_default_workspace(session)
    account = PaperAccount(team_id=workspace.team.id, name="默认模拟盘", cash=100000)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _core_event(session: Session, account: PaperAccount, topic: str, sequence: int, payload: dict) -> CoreEventLog:
    event = CoreEventLog(
        team_id=account.team_id,
        event_id=f"{topic}-{sequence}",
        topic=topic,
        sequence=sequence,
        correlation_id="paper-run-test",
        payload_json=json.dumps(payload),
        published_at=datetime(2026, 6, 13, tzinfo=timezone.utc) + timedelta(seconds=sequence),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def _filled_buy(session: Session, account: PaperAccount, ticker: str = "NVDA") -> PaperOrder:
    order = PaperOrder(
        account_id=account.id,
        team_id=account.team_id,
        ticker=ticker,
        side=PaperOrderSide.buy,
        quantity=1,
        status=PaperOrderStatus.filled,
        fill_price=100,
        risk_status="approved",
        risk_code="approved",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def _review(
    session: Session,
    account: PaperAccount,
    trading_day: str,
    equity: float,
    created_at: datetime,
) -> PaperReview:
    review = PaperReview(
        account_id=account.id,
        team_id=account.team_id,
        trading_day=trading_day,
        equity=equity,
        cash=equity,
        realized_pnl=0,
        unrealized_pnl=0,
        trade_count=1,
        win_rate=0,
        average_win=0,
        average_loss=0,
        expectancy=0,
        readiness=PaperReadiness.collecting,
        notes="test",
        created_at=created_at,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


def test_strategy_attribution_reports_data_quality_warnings_without_history():
    with make_session() as session:
        attribution = attribute_current_paper_strategy(session)

        assert attribution.strategy_id == "deterministic_watchlist_v1"
        assert attribution.signal_quality.market_event_count == 0
        assert attribution.signal_quality.trade_intent_count == 0
        assert attribution.regime.regime == "insufficient_data"
        assert attribution.drawdown.source == "insufficient_data"
        assert "missing_market_events" in attribution.data_quality_warnings
        assert "insufficient_review_history" in attribution.data_quality_warnings


def test_strategy_attribution_counts_signal_quality_from_core_events():
    with make_session() as session:
        account = _account(session)
        _core_event(session, account, "market_event", 1, {"ticker": "NVDA", "confidence": 0.8})
        _core_event(session, account, "market_event", 2, {"ticker": "MSFT", "confidence": 0.6})
        _core_event(session, account, "trade_intent", 3, {"ticker": "NVDA", "side": "buy"})

        attribution = attribute_current_paper_strategy(session)

        assert attribution.signal_quality.market_event_count == 2
        assert attribution.signal_quality.trade_intent_count == 1
        assert attribution.signal_quality.actionable_signal_rate == 0.5
        assert attribution.signal_quality.average_confidence == 0.7


def test_strategy_attribution_flags_losing_open_position_as_false_positive():
    with make_session() as session:
        account = _account(session)
        _filled_buy(session, account)
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=90,
                market_value=90,
                unrealized_pnl=-10,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)

        assert attribution.signal_quality.false_positive_rate == 1.0
        assert attribution.expectancy_decomposition.unrealized_pnl == -10
        assert attribution.expectancy_decomposition.open_trade_component == -10
        assert attribution.expectancy_decomposition.total_observed_pnl == -10


def test_strategy_attribution_identifies_drawdown_regime_and_source():
    with make_session() as session:
        account = _account(session)
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        _review(session, account, "2026-06-01", 100000, start)
        _review(session, account, "2026-06-02", 112000, start + timedelta(days=1))
        _review(session, account, "2026-06-03", 99000, start + timedelta(days=2))
        session.add(
            PaperPosition(
                account_id=account.id,
                team_id=account.team_id,
                ticker="NVDA",
                quantity=1,
                average_cost=100,
                last_price=90,
                market_value=90,
                unrealized_pnl=-10,
            )
        )
        session.commit()

        attribution = attribute_current_paper_strategy(session)

        assert attribution.regime.regime == "drawdown_pressure"
        assert attribution.regime.review_count == 3
        assert attribution.drawdown.source == "open_position_pressure"
        assert attribution.drawdown.max_drawdown == 0.1161
