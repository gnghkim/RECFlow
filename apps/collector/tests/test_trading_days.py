from datetime import date

from rec.trading_days import trading_days


def test_returns_only_tuesdays_and_thursdays():
    days = trading_days(date(2026, 8, 3), date(2026, 8, 9))
    assert days == [date(2026, 8, 4), date(2026, 8, 6)]


def test_includes_boundaries():
    days = trading_days(date(2026, 8, 4), date(2026, 8, 6))
    assert days == [date(2026, 8, 4), date(2026, 8, 6)]


def test_empty_when_range_has_no_trading_day():
    assert trading_days(date(2026, 8, 7), date(2026, 8, 9)) == []


def test_returns_empty_when_start_after_end():
    assert trading_days(date(2026, 8, 9), date(2026, 8, 3)) == []


def test_three_years_is_about_310_days():
    days = trading_days(date(2023, 8, 12), date(2026, 8, 12))
    assert 300 <= len(days) <= 320
