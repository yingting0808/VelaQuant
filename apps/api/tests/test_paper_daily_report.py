from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import (
    PaperAccount,
    PaperCandidate,
    PaperCandidateStatus,
    PaperPosition,
    PaperReview,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
)
from app.services import paper_daily_report
from app.services import paper_operations
from app.services.paper_daily_report import get_paper_daily_report
from app.services.paper_trading import PaperOrderCreate, run_daily_paper_trading_loop, submit_paper_order
from tests.test_paper_trading_service import FixtureProvider


def test_paper_daily_report_summarizes_runtime_facts_after_daily_run():
    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider)

        report = get_paper_daily_report(session, provider)

        assert report.trading_day
        assert report.run_state == "completed"
        assert report.health_status == "ready"
        assert report.recommended_action == "hold_until_next_session"
        assert report.candidate_count > 0
        assert report.order_count > 1
        assert report.open_position_count == report.order_count
        assert report.account_equity == 100000
        assert report.event_ledger_ready is True
        assert report.alpha_ready is False
        assert "review_day_sample" in report.alpha_blockers
        filled_gate = next(item for item in report.open_alpha_gates if item.gate == "filled_order_sample")
        assert filled_gate.label == "成交订单"
        assert filled_gate.current < filled_gate.required
        assert filled_gate.remaining > 0
        closed_gate = next(item for item in report.open_alpha_gates if item.gate == "closed_trade_sample")
        assert closed_gate.label == "闭环交易"
        assert closed_gate.remaining > 0


def test_paper_daily_report_breaks_down_candidate_quality_counts():
    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider)
        candidates = list(session.exec(select(PaperCandidate).order_by(PaperCandidate.rank)).all())
        assert len(candidates) >= 3
        candidates[0].status = PaperCandidateStatus.proposed
        candidates[1].status = PaperCandidateStatus.ordered
        for candidate in candidates[2:]:
            candidate.status = PaperCandidateStatus.dismissed
        session.add_all(candidates)
        session.commit()

        report = get_paper_daily_report(session, provider)

        assert report.candidate_count == len(candidates)
        assert report.actionable_candidate_count == 1
        assert report.ordered_candidate_count == 1
        assert report.dismissed_candidate_count == len(candidates) - 2


def test_paper_daily_report_surfaces_exit_watchlist_for_open_positions():
    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 115.0
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))
        submit_paper_order(session, provider, PaperOrderCreate(ticker="MSFT", side="buy", quantity=2))
        provider.prices["MSFT"] = 180.0
        submit_paper_order(session, provider, PaperOrderCreate(ticker="MSFT", side="sell", quantity=1))

        report = get_paper_daily_report(session, provider)

        aapl = next(item for item in report.exit_watchlist if item.ticker == "AAPL")
        assert aapl.trigger == "take_profit"
        assert aapl.triggered is True
        assert aapl.return_pct == 0.15
        assert aapl.next_exit_quantity == 1
        msft = next(item for item in report.exit_watchlist if item.ticker == "MSFT")
        assert msft.trigger == "stop_loss"
        assert msft.triggered is True
        assert msft.return_pct == -0.1
        assert msft.next_exit_quantity == 1


def test_paper_daily_report_exit_watchlist_uses_current_positions_when_report_is_as_of_prior_trading_day(monkeypatch):
    monkeypatch.setattr(paper_operations, "current_market_trading_day", lambda: "2026-06-12")

    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="AAPL", side="buy", quantity=2),
            trading_day="2026-06-13",
        )
        provider.prices["AAPL"] = 115.0
        submit_paper_order(
            session,
            provider,
            PaperOrderCreate(ticker="AAPL", side="sell", quantity=1),
            trading_day="2026-06-13",
        )

        report = get_paper_daily_report(session, provider)

        assert report.trading_day == "2026-06-12"
        aapl = next(item for item in report.exit_watchlist if item.ticker == "AAPL")
        assert aapl.trigger == "take_profit"
        assert aapl.triggered is True


def test_paper_daily_report_builds_exit_watchlist_without_second_summary_call(monkeypatch):
    calls = 0
    original_get_summary = paper_daily_report.get_paper_trading_summary

    def spy_get_summary(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_get_summary(*args, **kwargs)

    monkeypatch.setattr(paper_daily_report, "get_paper_trading_summary", spy_get_summary)

    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 115.0

        report = get_paper_daily_report(session, provider)

        assert calls == 1
        assert any(item.ticker == "AAPL" for item in report.exit_watchlist)


def test_paper_daily_report_exit_watchlist_projects_from_filled_orders_when_position_table_is_stale():
    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 115.0
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))
        for position in session.exec(select(PaperPosition)).all():
            session.delete(position)
        session.commit()

        report = get_paper_daily_report(session, provider)

        aapl = next(item for item in report.exit_watchlist if item.ticker == "AAPL")
        assert aapl.trigger == "take_profit"
        assert aapl.triggered is True
        assert aapl.quantity == 1


def test_paper_daily_report_uses_stored_paper_marks_without_live_quote_dependency():
    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        provider.prices["AAPL"] = 115.0
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="sell", quantity=1))

        def fail_live_quote(ticker: str):
            raise AssertionError(f"daily report should not request live quote for {ticker}")

        provider.get_quote = fail_live_quote

        report = get_paper_daily_report(session, provider)

        aapl = next(item for item in report.exit_watchlist if item.ticker == "AAPL")
        assert aapl.trigger == "take_profit"
        assert aapl.return_pct == 0.15
        assert aapl.quantity == 1


def test_paper_daily_report_surfaces_next_actionable_sample_and_alpha_forecast(monkeypatch):
    skipped_cron = datetime(2026, 6, 15, 6, 30, tzinfo=timezone.utc)
    actionable_cron = datetime(2026, 6, 16, 6, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(
        paper_daily_report,
        "get_paper_scheduler_status",
        lambda: SimpleNamespace(
            running=True,
            next_run_at=skipped_cron,
            next_run_will_execute=False,
            next_run_execution_gate="market_closed",
            next_actionable_run_at=actionable_cron,
            next_actionable_trading_day="2026-06-15",
            next_actionable_execution_gate="ready_to_run",
        ),
    )

    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider)

        report = get_paper_daily_report(session, provider)

        assert report.scheduler_next_run_at == skipped_cron
        assert report.scheduler_next_run_will_execute is False
        assert report.scheduler_next_run_execution_gate == "market_closed"
        assert report.scheduler_next_actionable_run_at == actionable_cron
        assert report.scheduler_next_actionable_trading_day == "2026-06-15"
        assert report.scheduler_next_actionable_execution_gate == "ready_to_run"
        assert report.estimated_sessions_to_alpha_ready is None
        assert report.limiting_alpha_gate is not None


def test_paper_daily_report_ignores_future_simulation_reviews(monkeypatch):
    monkeypatch.setattr(paper_operations, "current_market_trading_day", lambda: "2026-06-13")

    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-13")
        account = session.exec(select(PaperAccount)).one()
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-30",
                equity=103000,
                cash=100000,
                realized_pnl=500,
                unrealized_pnl=200,
                trade_count=10,
                win_rate=0.8,
                average_win=80,
                average_loss=10,
                expectancy=49.8,
                notes="future simulation review",
                created_at=datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.add(
            PaperRun(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-30",
                trigger=PaperRunTrigger.manual,
                status=PaperRunStatus.completed,
            )
        )
        session.commit()

        report = get_paper_daily_report(session, provider)

        assert report.trading_day == "2026-06-13"
        assert report.latest_expectancy == 0
        assert "future_runs_excluded_from_as_of_report" in report.data_quality_warnings
        assert "49.80" not in report.summary


def test_paper_daily_report_does_not_warn_for_quarantined_future_simulation_runs(monkeypatch):
    monkeypatch.setattr(paper_operations, "current_market_trading_day", lambda: "2026-06-13")

    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-13")
        account = session.exec(select(PaperAccount)).one()
        session.add(
            PaperRun(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-30",
                trigger=PaperRunTrigger.simulation,
                status=PaperRunStatus.completed,
            )
        )
        session.commit()

        report = get_paper_daily_report(session, provider)

        assert report.trading_day == "2026-06-13"
        assert "future_runs_excluded_from_as_of_report" not in report.data_quality_warnings


def test_paper_daily_report_includes_latest_daily_pnl(monkeypatch):
    monkeypatch.setattr(paper_operations, "current_market_trading_day", lambda: "2026-06-13")

    with make_session() as session:
        provider = FixtureProvider()
        run_daily_paper_trading_loop(session, provider, trading_day="2026-06-13")
        account = session.exec(select(PaperAccount)).one()
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-12",
                equity=100500,
                cash=100000,
                realized_pnl=100,
                unrealized_pnl=20,
                trade_count=1,
                win_rate=1,
                average_win=100,
                average_loss=0,
                expectancy=100,
                notes="prior review",
                created_at=datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc),
            )
        )
        latest = session.exec(select(PaperReview).where(PaperReview.trading_day == "2026-06-13")).one()
        latest.equity = 100780
        latest.realized_pnl = 130
        latest.unrealized_pnl = 50
        latest.created_at = datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc)
        session.add(latest)
        session.commit()

        report = get_paper_daily_report(session, provider)

        assert report.daily_pnl == 280
        assert report.daily_return == 0.0028


def test_paper_daily_report_uses_strategy_alpha_expectancy_not_account_review(monkeypatch):
    monkeypatch.setattr(paper_operations, "current_market_trading_day", lambda: "2026-06-13")
    monkeypatch.setattr("app.services.alpha_validation._has_real_market_backtest", lambda strategy_id: True)

    with make_session() as session:
        provider = FixtureProvider()
        submit_paper_order(session, provider, PaperOrderCreate(ticker="AAPL", side="buy", quantity=2))
        account = session.exec(select(PaperAccount)).one()
        session.add(
            PaperReview(
                account_id=account.id,
                team_id=account.team_id,
                trading_day="2026-06-13",
                equity=101000,
                cash=99000,
                realized_pnl=1000,
                unrealized_pnl=0,
                trade_count=4,
                win_rate=1,
                average_win=250,
                average_loss=0,
                expectancy=250,
                notes="account-level review is positive but strategy has no closed trade",
                created_at=datetime(2026, 6, 13, 21, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

        report = get_paper_daily_report(session, provider)

        assert report.daily_pnl == 0
        assert report.latest_expectancy == 0
        assert report.average_expectancy == 0
        assert report.consecutive_positive_expectancy_days == 0
        assert "latest_positive_expectancy" in report.alpha_blockers
        assert "latest expectancy 0.00" in report.summary


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
