"""US equity market hours (ET) with PC-local display times."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

MarketStatus = Literal["OPEN", "CLOSED", "PRE_MARKET", "AFTER_HOURS", "WEEKEND"]

US_EASTERN = ZoneInfo("America/New_York")
TRADING_HOURS_PER_DAY = 6.5

US_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}


def now_local() -> datetime:
    """Current time in the PC's local timezone (naive local)."""
    return datetime.now()


def utc_now() -> datetime:
    """Current UTC time (naive UTC) for market session comparison."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_from_utc(utc_naive: datetime) -> datetime:
    """Convert naive UTC to naive PC local time."""
    aware = utc_naive.replace(tzinfo=timezone.utc)
    return aware.astimezone().replace(tzinfo=None)


def utc_from_local(local_naive: datetime) -> datetime:
    """Convert naive PC local time to naive UTC."""
    ts = local_naive.timestamp()
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def is_us_holiday(d: date) -> bool:
    return d in US_HOLIDAYS_2026


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and not is_us_holiday(d)


def market_open_utc(d: date) -> datetime:
    """9:30 AM ET on date d, as naive UTC."""
    local_open = datetime.combine(d, time(9, 30), tzinfo=US_EASTERN)
    return local_open.astimezone(timezone.utc).replace(tzinfo=None)


def market_close_utc(d: date) -> datetime:
    """4:00 PM ET on date d, as naive UTC."""
    local_close = datetime.combine(d, time(16, 0), tzinfo=US_EASTERN)
    return local_close.astimezone(timezone.utc).replace(tzinfo=None)


def _next_trading_date(from_date: date) -> date:
    d = from_date + timedelta(days=1)
    for _ in range(366):
        if is_trading_day(d):
            return d
        d += timedelta(days=1)
    return d


def next_trading_open_utc(from_utc: datetime) -> datetime:
    """Next regular session open at or after from_utc."""
    d = from_utc.date()
    if is_trading_day(d):
        open_t = market_open_utc(d)
        if from_utc <= open_t:
            return open_t
        close_t = market_close_utc(d)
        if from_utc < close_t:
            return from_utc
    d = _next_trading_date(d if not is_trading_day(d) else d)
    return market_open_utc(d)


def next_trading_close_utc(from_utc: datetime) -> datetime:
    """Next regular session close strictly after from_utc."""
    d = from_utc.date()
    if is_trading_day(d):
        close_t = market_close_utc(d)
        open_t = market_open_utc(d)
        if from_utc < open_t:
            return close_t
        if from_utc < close_t:
            return close_t
    d = _next_trading_date(d)
    return market_close_utc(d)


def format_clock(dt: datetime) -> str:
    hour = dt.strftime("%I").lstrip("0") or "12"
    return f"{hour}:{dt.strftime('%M')} {dt.strftime('%p')}"


def format_event_local(event_local: datetime, now_local: datetime) -> str:
    delta_days = (event_local.date() - now_local.date()).days
    if delta_days == 0:
        return f"Today {format_clock(event_local)}"
    if delta_days == 1:
        return f"Tomorrow {format_clock(event_local)}"
    if delta_days < 7:
        return f"{event_local.strftime('%A')} {format_clock(event_local)}"
    return f"{event_local.strftime('%b')} {event_local.day}, {event_local.year} {format_clock(event_local)}"


def format_time_until(delta: timedelta) -> str:
    total_minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def get_market_status(now_local: datetime | None = None) -> dict:
    """
    US market status using UTC session boundaries; all display fields in PC local time.
    """
    if now_local is None:
        now_local = datetime.now()
    now_utc = utc_from_local(now_local)
    is_weekend = now_utc.weekday() >= 5

    if is_weekend:
        next_open_utc = next_trading_open_utc(now_utc)
        next_local = local_from_utc(next_open_utc)
        return {
            "status": "WEEKEND",
            "next_event": "Opens",
            "next_event_local": format_event_local(next_local, now_local),
            "next_event_datetime": next_local.isoformat(),
            "time_until": format_time_until(next_open_utc - now_utc),
            "is_weekend": True,
        }

    today = now_utc.date()
    if is_us_holiday(today):
        next_open_utc = next_trading_open_utc(now_utc)
        next_local = local_from_utc(next_open_utc)
        return {
            "status": "CLOSED",
            "next_event": "Opens",
            "next_event_local": format_event_local(next_local, now_local),
            "next_event_datetime": next_local.isoformat(),
            "time_until": format_time_until(next_open_utc - now_utc),
            "is_weekend": False,
        }

    open_utc = market_open_utc(today)
    close_utc = market_close_utc(today)

    if now_utc < open_utc:
        status: MarketStatus = "PRE_MARKET"
        next_utc = open_utc
        next_event = "Opens"
    elif now_utc < close_utc:
        status = "OPEN"
        next_utc = close_utc
        next_event = "Closes"
    elif now_utc.weekday() == 4:
        status = "AFTER_HOURS"
        next_utc = next_trading_open_utc(now_utc)
        next_event = "Opens"
    else:
        status = "CLOSED"
        next_utc = next_trading_open_utc(now_utc)
        next_event = "Opens"

    next_local = local_from_utc(next_utc)
    return {
        "status": status,
        "next_event": next_event,
        "next_event_local": format_event_local(next_local, now_local),
        "next_event_datetime": next_local.isoformat(),
        "time_until": format_time_until(next_utc - now_utc),
        "is_weekend": False,
    }



def calculate_trading_time(estimated_hours: float, now_local: datetime | None = None) -> datetime:
    """
    Advance estimated_hours counting only regular US session hours (6.5h/day).
    Skips nights, weekends, and US holidays. Returns naive PC local datetime.
    """
    if now_local is None:
        now_local = datetime.now()
    remaining = max(0.0, float(estimated_hours))
    cursor_utc = utc_from_local(now_local)

    for _ in range(5000):
        if remaining <= 1e-9:
            break

        if not is_trading_day(cursor_utc.date()):
            cursor_utc = market_open_utc(_next_trading_date(cursor_utc.date()))
            continue

        open_utc = market_open_utc(cursor_utc.date())
        close_utc = market_close_utc(cursor_utc.date())

        if cursor_utc < open_utc:
            cursor_utc = open_utc
            continue
        if cursor_utc >= close_utc:
            cursor_utc = market_open_utc(_next_trading_date(cursor_utc.date()))
            continue

        available = (close_utc - cursor_utc).total_seconds() / 3600.0
        chunk = min(remaining, available)
        cursor_utc += timedelta(hours=chunk)
        remaining -= chunk

    return local_from_utc(cursor_utc)


def is_market_open_now(now_local: datetime | None = None) -> bool:
    return get_market_status(now_local)["status"] == "OPEN"
