import json
from datetime import datetime, timezone

from sqlmodel import SQLModel, Session, create_engine, select

from app.core.config import Settings
from app.domain.models import CoreEventLog, PaperRun, PaperRunTrigger
from app.services import paper_scheduler
from app.services.market_calendar import MarketSessionStatus
from app.services.paper_scheduler import (
    get_paper_scheduler_status,
    run_scheduled_paper_trading_once,
    shutdown_paper_scheduler,
    start_paper_scheduler,
)


def test_paper_scheduler_is_disabled_by_default():
    settings = Settings(paper_scheduler_enabled=False)

    scheduler = start_paper_scheduler(settings)
    status = get_paper_scheduler_status(settings)

    assert scheduler is None
    assert status.enabled is False
    assert status.running is False
    assert status.job_count == 0
    assert status.job_id == "paper_trading_daily_run"
    assert status.next_run_at is None
    assert status.last_checked_at is not None


def test_paper_scheduler_registers_daily_job_when_enabled():
    settings = Settings(
        paper_scheduler_enabled=True,
        paper_scheduler_cron="30 6 * * *",
        paper_scheduler_timezone="Asia/Shanghai",
    )

    scheduler = start_paper_scheduler(settings)

    try:
        status = get_paper_scheduler_status(settings)
        assert scheduler is not None
        assert status.enabled is True
        assert status.running is True
        assert status.job_count == 1
        assert status.cron == "30 6 * * *"
        assert status.timezone == "Asia/Shanghai"
        assert status.job_id == "paper_trading_daily_run"
        assert status.next_run_at is not None
        assert status.last_checked_at is not None
        assert scheduler.get_job("paper_trading_daily_run") is not None
    finally:
        shutdown_paper_scheduler()


def test_paper_scheduler_status_exposes_market_execution_gate(monkeypatch):
    monkeypatch.setattr(
        paper_scheduler,
        "get_market_session_status",
        lambda: MarketSessionStatus(
            market_date="2026-06-13",
            trading_day="2026-06-12",
            is_market_session=False,
            session_closed=False,
            calendar_provider="pandas_market_calendars",
            reason="market_closed",
        ),
    )

    status = get_paper_scheduler_status(Settings(paper_scheduler_enabled=True))

    assert status.can_run_now is False
    assert status.market_date == "2026-06-13"
    assert status.trading_day == "2026-06-12"
    assert status.gate_reason == "market_closed"
    assert status.execution_gate == "market_closed"
    assert status.calendar_provider == "pandas_market_calendars"


def test_paper_scheduler_status_marks_next_cron_when_market_will_still_be_closed(monkeypatch):
    next_run_at = datetime(2026, 6, 15, 6, 30, tzinfo=timezone.utc)

    class Job:
        next_run_time = next_run_at

    class Scheduler:
        running = True

        def get_job(self, job_id):
            return Job()

        def get_jobs(self):
            return [Job()]

    def market_status(now=None):
        if now is next_run_at:
            return MarketSessionStatus(
                market_date="2026-06-14",
                trading_day="2026-06-12",
                is_market_session=False,
                session_closed=False,
                calendar_provider="pandas_market_calendars",
                reason="market_closed",
            )
        return MarketSessionStatus(
            market_date="2026-06-14",
            trading_day="2026-06-12",
            is_market_session=False,
            session_closed=False,
            calendar_provider="pandas_market_calendars",
            reason="market_closed",
        )

    monkeypatch.setattr(paper_scheduler, "_scheduler", Scheduler())
    monkeypatch.setattr(paper_scheduler, "get_market_session_status", market_status)

    status = get_paper_scheduler_status(Settings(paper_scheduler_enabled=True))

    assert status.next_run_at == next_run_at
    assert status.next_run_will_execute is False
    assert status.next_run_execution_gate == "market_closed"
    assert status.next_run_trading_day == "2026-06-12"
    assert status.next_run_gate_reason == "market_closed"


def test_scheduled_job_runs_paper_loop_with_scheduled_trigger(monkeypatch):
    captured = {}

    class Provider:
        def close(self):
            captured["closed"] = True

    class SessionContext:
        def __enter__(self):
            return "session"

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(paper_scheduler, "build_market_data_provider", lambda settings: Provider())
    monkeypatch.setattr(paper_scheduler, "get_market_session_status", _closed_session_status)
    monkeypatch.setattr(paper_scheduler, "Session", lambda engine: SessionContext())
    monkeypatch.setattr(
        paper_scheduler,
        "run_daily_paper_trading_loop",
        lambda session, provider, trigger=PaperRunTrigger.manual: captured.update(
            {"session": session, "trigger": trigger}
        ),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "record_shadow_observation",
        lambda session: captured.update({"shadow_session": session}),
    )

    result = run_scheduled_paper_trading_once()

    assert result.executed is True
    assert result.reason == "current_session_closed"
    assert result.trading_day == "2026-06-15"
    assert captured["session"] == "session"
    assert captured["trigger"] == PaperRunTrigger.scheduled
    assert captured["shadow_session"] == "session"
    assert captured["closed"] is True


def test_scheduled_job_skips_shadow_observation_when_lifecycle_gate_blocks(monkeypatch):
    captured = {}

    class Provider:
        def close(self):
            captured["closed"] = True

    class SessionContext:
        def __enter__(self):
            return "session"

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(paper_scheduler, "build_market_data_provider", lambda settings: Provider())
    monkeypatch.setattr(paper_scheduler, "get_market_session_status", _closed_session_status)
    monkeypatch.setattr(paper_scheduler, "Session", lambda engine: SessionContext())
    monkeypatch.setattr(
        paper_scheduler,
        "run_daily_paper_trading_loop",
        lambda session, provider, trigger=PaperRunTrigger.manual: captured.update(
            {"session": session, "trigger": trigger}
        ),
    )

    def blocked_shadow_record(session):
        captured["shadow_session"] = session
        raise ValueError("Shadow observation requires current lifecycle stage shadow.")

    monkeypatch.setattr(paper_scheduler, "record_shadow_observation", blocked_shadow_record)

    result = run_scheduled_paper_trading_once()

    assert result.executed is True
    assert result.reason == "current_session_closed"
    assert captured["session"] == "session"
    assert captured["trigger"] == PaperRunTrigger.scheduled
    assert captured["shadow_session"] == "session"
    assert captured["closed"] is True


def test_scheduled_job_skips_when_market_session_has_not_closed(monkeypatch):
    captured = {}
    monkeypatch.setattr(paper_scheduler, "engine", _isolated_db_engine())

    monkeypatch.setattr(
        paper_scheduler,
        "get_market_session_status",
        lambda: MarketSessionStatus(
            market_date="2026-06-13",
            trading_day="2026-06-12",
            is_market_session=True,
            session_closed=False,
            calendar_provider="pandas_market_calendars",
            reason="current_session_not_closed",
        ),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "build_market_data_provider",
        lambda settings: captured.update({"provider_built": True}),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "run_daily_paper_trading_loop",
        lambda *args, **kwargs: captured.update({"ran": True}),
    )

    result = run_scheduled_paper_trading_once()

    assert result.executed is False
    assert result.market_date == "2026-06-13"
    assert result.trading_day == "2026-06-12"
    assert result.reason == "current_session_not_closed"
    assert captured == {}


def test_scheduled_job_skips_when_market_is_closed(monkeypatch):
    captured = {}
    monkeypatch.setattr(paper_scheduler, "engine", _isolated_db_engine())

    monkeypatch.setattr(
        paper_scheduler,
        "get_market_session_status",
        lambda: MarketSessionStatus(
            market_date="2026-06-13",
            trading_day="2026-06-12",
            is_market_session=False,
            session_closed=False,
            calendar_provider="pandas_market_calendars",
            reason="market_closed",
        ),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "build_market_data_provider",
        lambda settings: captured.update({"provider_built": True}),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "run_daily_paper_trading_loop",
        lambda *args, **kwargs: captured.update({"ran": True}),
    )

    result = run_scheduled_paper_trading_once()

    assert result.executed is False
    assert result.market_date == "2026-06-13"
    assert result.trading_day == "2026-06-12"
    assert result.reason == "market_closed"
    assert captured == {}


def test_scheduled_job_persists_market_guard_decision_without_paper_run(monkeypatch):
    captured = {}
    db_engine = _isolated_db_engine()

    monkeypatch.setattr(paper_scheduler, "engine", db_engine)
    monkeypatch.setattr(
        paper_scheduler,
        "get_market_session_status",
        lambda: MarketSessionStatus(
            market_date="2026-06-13",
            trading_day="2026-06-12",
            is_market_session=False,
            session_closed=False,
            calendar_provider="pandas_market_calendars",
            reason="market_closed",
        ),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "build_market_data_provider",
        lambda settings: captured.update({"provider_built": True}),
    )
    monkeypatch.setattr(
        paper_scheduler,
        "run_daily_paper_trading_loop",
        lambda *args, **kwargs: captured.update({"ran": True}),
    )

    result = run_scheduled_paper_trading_once()

    with Session(db_engine) as session:
        events = session.exec(select(CoreEventLog)).all()
        runs = session.exec(select(PaperRun)).all()

    assert result.executed is False
    assert captured == {}
    assert runs == []
    assert len(events) == 1
    assert events[0].run_id is None
    assert events[0].topic == "scheduler_decision"
    assert events[0].correlation_id == "paper_scheduler:2026-06-13"
    payload = json.loads(events[0].payload_json)
    assert payload["executed"] is False
    assert payload["execution_gate"] == "market_closed"
    assert payload["reason"] == "market_closed"
    assert payload["trading_day"] == "2026-06-12"


def _closed_session_status() -> MarketSessionStatus:
    return MarketSessionStatus(
        market_date="2026-06-15",
        trading_day="2026-06-15",
        is_market_session=True,
        session_closed=True,
        calendar_provider="pandas_market_calendars",
        reason="current_session_closed",
    )


def _isolated_db_engine():
    db_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(db_engine)
    return db_engine
