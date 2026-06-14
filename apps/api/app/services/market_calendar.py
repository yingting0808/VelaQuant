from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo


MARKET_CALENDAR_NAME = "NYSE"
MARKET_TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_SESSION_CLOSE = time(16, 0)
TRADING_DAY_MODE_ENV = "AI_STOCKS_TRADING_DAY_MODE"


@dataclass(frozen=True)
class MarketSessionStatus:
    market_date: str
    trading_day: str
    is_market_session: bool
    session_closed: bool
    calendar_provider: str
    reason: str


def current_market_trading_day(now: datetime | None = None, mode: str | None = None) -> str:
    resolved_mode = mode or os.getenv(TRADING_DAY_MODE_ENV, "utc")
    if resolved_mode == "utc" and now is None:
        return datetime.now(timezone.utc).date().isoformat()
    return get_market_session_status(now=now).trading_day


def get_market_session_status(now: datetime | None = None) -> MarketSessionStatus:
    market_now = _market_now(now)
    market_date = market_now.date()
    session = _session_for_date(market_date)
    is_session = session is not None
    session_closed = bool(session is not None and market_now >= session.close_at)

    if session_closed:
        return MarketSessionStatus(
            market_date=market_date.isoformat(),
            trading_day=market_date.isoformat(),
            is_market_session=True,
            session_closed=True,
            calendar_provider=session.provider,
            reason="current_session_closed",
        )

    previous_session = _previous_session(market_date)
    return MarketSessionStatus(
        market_date=market_date.isoformat(),
        trading_day=previous_session.session_date.isoformat(),
        is_market_session=is_session,
        session_closed=False,
        calendar_provider=previous_session.provider,
        reason="current_session_not_closed" if is_session else "market_closed",
    )


@dataclass(frozen=True)
class _MarketSession:
    session_date: date
    close_at: datetime
    provider: str


def _market_now(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(MARKET_TIMEZONE)


def _previous_session(market_date: date) -> _MarketSession:
    cursor = market_date - timedelta(days=1)
    for _ in range(14):
        session = _session_for_date(cursor)
        if session is not None:
            return session
        cursor -= timedelta(days=1)
    raise ValueError(f"No previous market session found before {market_date.isoformat()}.")


def _session_for_date(session_date: date) -> _MarketSession | None:
    pmc_session = _pandas_market_calendar_session(session_date)
    if pmc_session is not None:
        return pmc_session
    return _weekday_fallback_session(session_date)


def _pandas_market_calendar_session(session_date: date) -> _MarketSession | None:
    calendar = _pandas_market_calendar()
    if calendar is None:
        return None
    schedule = calendar.schedule(start_date=session_date.isoformat(), end_date=session_date.isoformat())
    if schedule.empty:
        return None
    close_value = schedule.iloc[0]["market_close"]
    close_at = close_value.to_pydatetime().astimezone(MARKET_TIMEZONE)
    return _MarketSession(session_date=session_date, close_at=close_at, provider="pandas_market_calendars")


@lru_cache(maxsize=1)
def _pandas_market_calendar():
    try:
        import pandas_market_calendars as market_calendars
    except ImportError:
        return None
    return market_calendars.get_calendar(MARKET_CALENDAR_NAME)


def _weekday_fallback_session(session_date: date) -> _MarketSession | None:
    if session_date.weekday() >= 5:
        return None
    close_at = datetime.combine(session_date, DEFAULT_SESSION_CLOSE, tzinfo=MARKET_TIMEZONE)
    return _MarketSession(session_date=session_date, close_at=close_at, provider="weekday_fallback")
