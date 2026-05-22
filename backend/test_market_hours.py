"""Market hours status and trading-time projection tests."""

import re
from datetime import datetime

from market_hours import (
    calculate_trading_time,
    format_clock,
    get_market_status,
    local_from_utc,
    market_open_utc,
    utc_from_local,
)
from signal_engine import format_timing_estimate


def test_market_closed_weeknight():
    """UTC ~11 PM Tuesday — market closed until next open."""
    # Tue May 19 2026 23:00 UTC = after US close
    now_utc = datetime(2026, 5, 19, 23, 0, 0)
    now_local = local_from_utc(now_utc)
    status = get_market_status(now_local)
    assert status["status"] == "CLOSED"
    assert status["next_event"] == "Opens"
    assert status["is_weekend"] is False
    assert "h" in status["time_until"] or "m" in status["time_until"]

    label = format_timing_estimate(22 / 24, now_local)
    assert "market hours only" in label
    assert "May" in label
    assert not re.search(r"\d+\s*hours", label.lower())


def test_market_open():
    """UTC 2 PM — regular session."""
    now_utc = datetime(2026, 5, 19, 14, 0, 0)
    now_local = local_from_utc(now_utc)
    status = get_market_status(now_local)
    assert status["status"] == "OPEN"
    assert status["next_event"] == "Closes"
    assert "h" in status["time_until"] or "m" in status["time_until"]

    label = format_timing_estimate(4 / 24, now_local)
    assert "Today" in label
    assert "market hours only" in label


def test_friday_after_close():
    """Friday after close — after hours; skip weekend and Memorial Day (May 25)."""
    now_utc = datetime(2026, 5, 22, 20, 0, 0)  # Fri 4 PM ET
    now_local = local_from_utc(now_utc)
    status = get_market_status(now_local)
    assert status["status"] == "AFTER_HOURS"
    assert status["is_weekend"] is False
    # May 25, 2026 is Memorial Day — next session is Tue May 26
    assert "Tuesday" in status["next_event_local"] or "May 26" in status["next_event_local"]

    arrival = calculate_trading_time(18, now_local)
    assert arrival.weekday() < 5
    assert arrival.date() >= datetime(2026, 5, 26).date()


def test_saturday_weekend():
    """Saturday — weekend status; next open skips Memorial Day Mon May 25."""
    now_utc = datetime(2026, 5, 23, 15, 0, 0)
    now_local = local_from_utc(now_utc)
    status = get_market_status(now_local)
    assert status["status"] == "WEEKEND"
    assert status["is_weekend"] is True
    assert "Tuesday" in status["next_event_local"] or "May 26" in status["next_event_local"]


def test_memorial_day_holiday():
    """May 25 2026 Memorial Day — skip to May 26."""
    now_utc = datetime(2026, 5, 25, 14, 0, 0)
    now_local = local_from_utc(now_utc)
    status = get_market_status(now_local)
    assert status["status"] == "CLOSED"
    assert status["is_weekend"] is False

    next_open = local_from_utc(market_open_utc(datetime(2026, 5, 26).date()))
    assert "May 26" in status["next_event_local"] or format_clock(next_open) in status["next_event_local"]

    arrival = calculate_trading_time(6.5, now_local)
    assert arrival.date().month == 5
    assert arrival.date().day >= 26


def test_calculate_trading_time_skips_closed_hours():
    """When market is closed, counting starts at next open."""
    now_utc = datetime(2026, 5, 19, 23, 0, 0)
    now_local = local_from_utc(now_utc)
    arrival = calculate_trading_time(1.0, now_local)
    open_local = local_from_utc(market_open_utc(datetime(2026, 5, 20).date()))
    assert arrival >= open_local


if __name__ == "__main__":
    test_market_closed_weeknight()
    test_market_open()
    test_friday_after_close()
    test_saturday_weekend()
    test_memorial_day_holiday()
    test_calculate_trading_time_skips_closed_hours()
    print("All market hours tests passed.")
