from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.market_calendar import current_market_trading_day, get_market_session_status


def test_current_market_trading_day_uses_latest_closed_us_session_after_close():
    now = datetime(2026, 6, 12, 17, 5, tzinfo=ZoneInfo("America/New_York"))

    assert current_market_trading_day(now=now) == "2026-06-12"


def test_current_market_trading_day_uses_previous_session_before_close():
    now = datetime(2026, 6, 12, 10, 5, tzinfo=ZoneInfo("America/New_York"))

    status = get_market_session_status(now=now)

    assert status.trading_day == "2026-06-11"
    assert status.reason == "current_session_not_closed"


def test_current_market_trading_day_uses_previous_session_on_weekend_from_shanghai_scheduler_time():
    now = datetime(2026, 6, 14, 6, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    status = get_market_session_status(now=now)

    assert status.market_date == "2026-06-13"
    assert status.trading_day == "2026-06-12"
    assert status.reason == "market_closed"

