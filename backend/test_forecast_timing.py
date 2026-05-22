"""ATR + volume timing → real date/time labels."""
import re
from datetime import datetime

from signal_engine import (
    build_forecasts,
    estimate_days_to_target,
    format_timing_estimate,
    timing_labels_for_target,
    volume_timing_factor,
)

NOW = datetime(2026, 5, 21, 14, 0, 0)


def test_volume_factors():
    assert volume_timing_factor(3.5) == 0.4
    assert volume_timing_factor(2.5) == 0.6
    assert volume_timing_factor(1.5) == 0.8
    assert volume_timing_factor(1.0) == 1.0
    assert volume_timing_factor(0.3) == 1.5


def test_no_raw_hours_or_days():
    label = format_timing_estimate(22 / 24, NOW)
    assert not re.search(r"\d+\s*hours", label.lower())
    assert " days" not in label.lower()
    assert "(market hours only, estimate only)" in label
    assert label.startswith("~")


def test_saic_tomorrow():
    # ~22 trading hours from 2 PM during session
    days = 22 / 24
    label = format_timing_estimate(days, NOW)
    assert "PM" in label or "AM" in label
    assert not re.search(r"\d+\s*hours", label.lower())


def test_ocgn_today_or_tomorrow():
    days = 18 / 24
    label = format_timing_estimate(days, NOW)
    assert "Today" in label or "Tomorrow" in label or "May" in label
    assert not re.search(r"\d+\s*hours", label.lower())


def test_dia_within_week_date():
    label = format_timing_estimate(3.0, NOW)
    assert "2026" in label
    assert "(market hours only, estimate only)" in label
    assert not re.search(r"\d+\s*hours", label.lower())


def test_beyond_seven_days_date_only():
    label = format_timing_estimate(10.0, NOW)
    assert "2026" in label
    assert "PM" not in label and "AM" not in label


def test_safety_rules():
    assert "unclear" in format_timing_estimate(None, NOW).lower()
    assert "Long-term" in format_timing_estimate(200, NOW)


def test_forecast_horizons_use_datetime_labels():
    features = {"price": 95.32, "atr": 1.13, "vol_ratio": 2.5, "ma_signal": "neutral"}
    fc = build_forecasts(features, "BUY", NOW)
    for key in (
        "short_term_forecast",
        "medium_term_forecast",
        "long_term_forecast",
        "monthly_forecast",
    ):
        pred = fc[key]["predicted_by"]
        assert "(market hours only, estimate only)" in pred
        assert not re.search(r"\d+\s*hours", pred.lower())
        assert " days" not in pred.lower()


def test_varied_volume_changes_timing():
    days_fast = estimate_days_to_target(95.32, 98.17, 1.13, 3.5)
    days_slow = estimate_days_to_target(95.32, 98.17, 1.13, 0.3)
    assert days_fast < days_slow


if __name__ == "__main__":
    test_volume_factors()
    test_no_raw_hours_or_days()
    test_saic_tomorrow()
    test_ocgn_today_or_tomorrow()
    test_dia_within_week_date()
    test_beyond_seven_days_date_only()
    test_safety_rules()
    test_forecast_horizons_use_datetime_labels()
    test_varied_volume_changes_timing()
    print("All timing tests passed.")
