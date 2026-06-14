from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import PaperAccount, PaperReview, PaperRun, PaperRunStatus, PaperRunTrigger
from app.services import paper_daily_report
from app.services import paper_operations
from app.services.paper_daily_report import get_paper_daily_report
from app.services.paper_trading import run_daily_paper_trading_loop
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


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)
