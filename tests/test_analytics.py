"""Unit tests for the shared month arithmetic.

Pure date math, so these pass an explicit `today` rather than depending on the
calendar the suite happens to run on.
"""

from datetime import date

import pytest

from services.analytics import month_bounds


@pytest.mark.parametrize("day", [1, 2, 15, 30])
def test_any_day_in_a_month_gives_the_same_bounds(day):
    assert month_bounds(date(2026, 9, day)) == (date(2026, 9, 1), date(2026, 10, 1))


def test_december_rolls_into_the_next_year():
    assert month_bounds(date(2026, 12, 31)) == (date(2026, 12, 1), date(2027, 1, 1))


def test_january_starts_the_year():
    assert month_bounds(date(2026, 1, 1)) == (date(2026, 1, 1), date(2026, 2, 1))


def test_february_in_a_leap_year():
    assert month_bounds(date(2028, 2, 29)) == (date(2028, 2, 1), date(2028, 3, 1))


def test_february_in_a_common_year():
    assert month_bounds(date(2026, 2, 28)) == (date(2026, 2, 1), date(2026, 3, 1))


@pytest.mark.parametrize("month", range(1, 13))
def test_every_month_produces_a_contiguous_range(month):
    start, end = month_bounds(date(2026, month, 1))
    assert start.day == 1
    assert end.day == 1
    assert start < end
    # The range ends exactly where the next month's begins: no gap, no overlap.
    assert month_bounds(end)[0] == end


def test_range_is_half_open_around_month_end():
    start, end = month_bounds(date(2026, 9, 15))
    assert start <= date(2026, 9, 30) < end
    assert not (start <= date(2026, 10, 1) < end)
    assert not (start <= date(2026, 8, 31) < end)


def test_defaults_to_the_current_month():
    today = date.today()
    start, end = month_bounds()
    assert start == today.replace(day=1)
    assert start <= today < end
