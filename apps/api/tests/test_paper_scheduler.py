from app.core.config import Settings
from app.domain.models import PaperRunTrigger
from app.services import paper_scheduler
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
        assert scheduler.get_job("paper_trading_daily_run") is not None
    finally:
        shutdown_paper_scheduler()


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
    monkeypatch.setattr(paper_scheduler, "Session", lambda engine: SessionContext())
    monkeypatch.setattr(
        paper_scheduler,
        "run_daily_paper_trading_loop",
        lambda session, provider, trigger=PaperRunTrigger.manual: captured.update(
            {"session": session, "trigger": trigger}
        ),
    )

    run_scheduled_paper_trading_once()

    assert captured["session"] == "session"
    assert captured["trigger"] == PaperRunTrigger.scheduled
    assert captured["closed"] is True
