from app.core.config import Settings
from app.services.paper_scheduler import get_paper_scheduler_status, shutdown_paper_scheduler, start_paper_scheduler


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
