from pydantic import BaseModel
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.data.providers.registry import build_market_data_provider
from app.db.session import engine
from app.domain.models import PaperRunTrigger
from app.services.paper_trading import run_daily_paper_trading_loop


class PaperSchedulerStatus(BaseModel):
    enabled: bool
    running: bool
    job_count: int
    cron: str
    timezone: str


_scheduler = None


def start_paper_scheduler(settings: Settings | None = None):
    global _scheduler
    settings = settings or get_settings()
    if not settings.paper_scheduler_enabled:
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone=settings.paper_scheduler_timezone)
    scheduler.add_job(
        run_scheduled_paper_trading_once,
        CronTrigger.from_crontab(settings.paper_scheduler_cron, timezone=settings.paper_scheduler_timezone),
        id="paper_trading_daily_run",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_paper_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def get_paper_scheduler_status(settings: Settings | None = None) -> PaperSchedulerStatus:
    settings = settings or get_settings()
    return PaperSchedulerStatus(
        enabled=settings.paper_scheduler_enabled,
        running=bool(_scheduler is not None and _scheduler.running),
        job_count=len(_scheduler.get_jobs()) if _scheduler is not None else 0,
        cron=settings.paper_scheduler_cron,
        timezone=settings.paper_scheduler_timezone,
    )


def run_scheduled_paper_trading_once() -> None:
    settings = get_settings()
    provider = build_market_data_provider(settings)
    try:
        with Session(engine) as session:
            run_daily_paper_trading_loop(session, provider, trigger=PaperRunTrigger.scheduled)
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()
