from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import PaperAccount, PaperOrder, PaperOrderSide, PaperOrderStatus, Team
from app.services.paper_execution_diagnostics import get_paper_execution_diagnostics


def test_paper_execution_diagnostics_handles_empty_orders():
    with make_session() as session:
        team = Team(name="Empty Execution")
        session.add(team)
        session.commit()
        session.refresh(team)

        diagnostics = get_paper_execution_diagnostics(session, team_id=team.id, as_of_trading_day="2026-06-17")

        assert diagnostics.order_count == 0
        assert diagnostics.filled_order_count == 0
        assert diagnostics.rejected_order_count == 0
        assert diagnostics.fill_rate == 0
        assert diagnostics.rejection_reasons == []
        assert diagnostics.max_daily_order_buy_rejections == 0
        assert diagnostics.max_daily_order_sell_rejections == 0
        assert diagnostics.summary == "No paper execution orders are available yet."


def test_paper_execution_diagnostics_summarizes_fills_rejections_and_realized_pnl():
    with make_session() as session:
        team = Team(name="Execution Diagnostics")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.filled,
                realized_pnl=0,
                submitted_at=datetime(2026, 6, 14, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _order(
                account,
                side=PaperOrderSide.sell,
                status=PaperOrderStatus.filled,
                realized_pnl=120,
                submitted_at=datetime(2026, 6, 15, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="max_daily_orders",
                rejection_reason="Orders today 5 reached limit 5.",
                submitted_at=datetime(2026, 6, 16, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _order(
                account,
                side=PaperOrderSide.sell,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="insufficient_quantity",
                rejection_reason="Insufficient paper quantity.",
                submitted_at=datetime(2026, 6, 17, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        diagnostics = get_paper_execution_diagnostics(session, team_id=team.id, as_of_trading_day="2026-06-17")

        assert diagnostics.order_count == 4
        assert diagnostics.filled_order_count == 2
        assert diagnostics.rejected_order_count == 2
        assert diagnostics.buy_order_count == 2
        assert diagnostics.sell_order_count == 2
        assert diagnostics.closed_trade_count == 1
        assert diagnostics.fill_rate == 0.5
        assert diagnostics.rejection_rate == 0.5
        assert diagnostics.realized_pnl == 120
        assert diagnostics.average_realized_pnl == 120
        assert diagnostics.latest_rejection_code == "insufficient_quantity"
        assert diagnostics.max_daily_order_rejections == 1
        assert diagnostics.max_daily_order_buy_rejections == 1
        assert diagnostics.max_daily_order_sell_rejections == 0
        assert diagnostics.rejection_reasons[0].risk_code == "insufficient_quantity"
        assert diagnostics.rejection_reasons[1].risk_code == "max_daily_orders"


def test_paper_execution_diagnostics_splits_daily_order_rejections_by_side():
    with make_session() as session:
        team = Team(name="Execution Diagnostics")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="max_daily_orders",
                rejection_reason="Orders today 5 reached limit 5.",
                submitted_at=datetime(2026, 6, 16, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _order(
                account,
                side=PaperOrderSide.sell,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="max_daily_orders",
                rejection_reason="Orders today 5 reached limit 5.",
                submitted_at=datetime(2026, 6, 17, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        diagnostics = get_paper_execution_diagnostics(session, team_id=team.id, as_of_trading_day="2026-06-17")

        assert diagnostics.max_daily_order_rejections == 2
        assert diagnostics.max_daily_order_buy_rejections == 1
        assert diagnostics.max_daily_order_sell_rejections == 1


def test_paper_execution_diagnostics_ignores_future_orders_for_as_of_trading_day():
    with make_session() as session:
        team = Team(name="Execution Diagnostics")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.filled,
                realized_pnl=0,
                submitted_at=datetime(2026, 6, 14, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="max_daily_orders",
                rejection_reason="Orders today 6 reached limit 6.",
                submitted_at=datetime(2026, 6, 20, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        diagnostics = get_paper_execution_diagnostics(session, team_id=team.id, as_of_trading_day="2026-06-14")

        assert diagnostics.order_count == 1
        assert diagnostics.rejected_order_count == 0
        assert diagnostics.max_daily_order_buy_rejections == 0


def test_paper_execution_diagnostics_defaults_to_current_market_trading_day(monkeypatch):
    with make_session() as session:
        team = Team(name="Execution Diagnostics")
        session.add(team)
        session.commit()
        session.refresh(team)
        account = PaperAccount(team_id=team.id, name="paper")
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.filled,
                realized_pnl=0,
                submitted_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            _order(
                account,
                side=PaperOrderSide.buy,
                status=PaperOrderStatus.rejected,
                realized_pnl=0,
                risk_code="max_daily_orders",
                rejection_reason="Orders today 6 reached limit 6.",
                submitted_at=datetime(2026, 6, 13, 11, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()
        monkeypatch.setattr(
            "app.services.paper_execution_diagnostics.current_market_trading_day",
            lambda: "2026-06-12",
        )

        diagnostics = get_paper_execution_diagnostics(session, team_id=team.id)

        assert diagnostics.order_count == 1
        assert diagnostics.rejected_order_count == 0
        assert diagnostics.max_daily_order_buy_rejections == 0


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _order(
    account: PaperAccount,
    *,
    side: PaperOrderSide,
    status: PaperOrderStatus,
    realized_pnl: float,
    submitted_at: datetime,
    risk_code: str | None = None,
    rejection_reason: str | None = None,
) -> PaperOrder:
    return PaperOrder(
        account_id=account.id,
        team_id=account.team_id,
        ticker="NVDA",
        side=side,
        order_type="market",
        quantity=1,
        status=status,
        fill_price=100 if status == PaperOrderStatus.filled else None,
        realized_pnl=realized_pnl,
        rejection_reason=rejection_reason,
        risk_status="rejected" if status == PaperOrderStatus.rejected else "approved",
        risk_code=risk_code or ("approved" if status == PaperOrderStatus.filled else "rejected"),
        submitted_at=submitted_at,
        filled_at=submitted_at if status == PaperOrderStatus.filled else None,
    )
