"""Unit tests for the shared month arithmetic.

Pure date math, so these pass an explicit `today` rather than depending on the
calendar the suite happens to run on.
"""

from datetime import date
from decimal import Decimal

import pytest

from services.analytics import (
    average_expense,
    budget_utilization,
    month_bounds,
    monthly_insights,
    spending_change,
    top_spending_category,
)


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


# --- deterministic monthly insights ------------------------------------------


def budget_entry(category, limit, spent):
    """A get_budget_status() row, trimmed to the fields insights read."""
    return {"category": category, "limit": Decimal(limit), "spent": Decimal(spent)}


@pytest.mark.parametrize(
    ("current", "previous", "delta", "percent"),
    [
        ("150.00", "100.00", "50.00", "50.0"),    # up by half
        ("75.00", "100.00", "-25.00", "-25.0"),   # down by a quarter
        ("100.00", "100.00", "0.00", "0.0"),      # unchanged
        ("0.00", "100.00", "-100.00", "-100.0"),  # stopped spending entirely
        ("33.00", "99.00", "-66.00", "-66.7"),    # rounds half-up to one place
    ],
)
def test_spending_change_against_a_month_with_spending(current, previous, delta, percent):
    result = spending_change(Decimal(current), Decimal(previous))
    assert result["delta"] == Decimal(delta)
    assert result["percent"] == Decimal(percent)


@pytest.mark.parametrize("previous", ["0.00", 0])
def test_spending_change_reports_no_percentage_without_a_baseline(previous):
    # "Up infinitely" from zero is arithmetic, not information.
    result = spending_change(Decimal("250.00"), previous)
    assert result["percent"] is None
    assert result["delta"] == Decimal("250.00")
    assert result["increased"] is True


def test_spending_change_from_nothing_to_nothing():
    result = spending_change(0, 0)
    assert result["delta"] == 0
    assert result["percent"] is None
    assert result["increased"] is False


def test_spending_change_flags_only_increases():
    assert spending_change(Decimal("10"), Decimal("5"))["increased"] is True
    assert spending_change(Decimal("5"), Decimal("10"))["increased"] is False
    assert spending_change(Decimal("5"), Decimal("5"))["increased"] is False


def test_average_expense_is_none_without_expenses():
    assert average_expense(0, 0) is None
    assert average_expense(Decimal("0.00"), 0) is None


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [("90.00", 3, "30.00"), ("20.00", 3, "6.67"), ("10.00", 4, "2.50"), ("5.00", 1, "5.00")],
)
def test_average_expense_rounds_to_two_places(total, count, expected):
    assert average_expense(Decimal(total), count) == Decimal(expected)


def test_top_spending_category_reads_the_first_row():
    # The breakdown arrives ordered by total descending; re-sorting here could
    # disagree with the list rendered directly below it.
    breakdown = [("Dining", Decimal("400.00")), ("Groceries", Decimal("120.00"))]
    assert top_spending_category(breakdown) == {
        "category": "Dining",
        "total": Decimal("400.00"),
    }


def test_top_spending_category_is_none_without_expenses():
    assert top_spending_category([]) is None


def test_budget_utilization_is_none_without_budgets():
    assert budget_utilization([]) is None


def test_budget_utilization_totals_every_budgeted_category():
    status = [
        budget_entry("Groceries", "200.00", "50.00"),
        budget_entry("Dining", "300.00", "75.00"),
    ]
    result = budget_utilization(status)

    assert result["spent"] == Decimal("125.00")
    assert result["limit"] == Decimal("500.00")
    assert result["percent"] == Decimal("25.0")
    assert result["over_budget"] is False


def test_budget_utilization_reports_over_budget_but_caps_the_bar():
    status = [budget_entry("Dining", "100.00", "175.00")]
    result = budget_utilization(status)

    assert result["percent"] == Decimal("175.0")       # the figure tells the truth
    assert result["display_percent"] == Decimal("100")  # the bar stops at full
    assert result["over_budget"] is True


def test_budget_utilization_handles_a_budget_with_no_spending():
    result = budget_utilization([budget_entry("Bills", "400.00", 0)])
    assert result["percent"] == Decimal("0.0")
    assert result["over_budget"] is False


def test_monthly_insights_assembles_every_figure():
    stats = {
        "current_total": Decimal("300.00"),
        "current_count": 3,
        "previous_total": Decimal("200.00"),
    }
    largest = {"source": "Rent", "date": date(2026, 9, 1), "amount": Decimal("180.00")}
    breakdown = [("Bills", Decimal("180.00")), ("Dining", Decimal("120.00"))]
    status = [budget_entry("Bills", "500.00", "180.00")]

    insights = monthly_insights(stats, largest, breakdown, status)

    assert set(insights) == {
        "spending_change",
        "top_category",
        "average_expense",
        "largest_expense",
        "budget_utilization",
        "expense_count",
    }
    assert insights["expense_count"] == 3
    assert insights["spending_change"]["percent"] == Decimal("50.0")
    assert insights["top_category"]["category"] == "Bills"
    assert insights["average_expense"] == Decimal("100.00")
    assert insights["largest_expense"] == largest
    assert insights["budget_utilization"]["percent"] == Decimal("36.0")


def test_monthly_insights_survives_a_completely_empty_month():
    stats = {"current_total": 0, "current_count": 0, "previous_total": 0}
    insights = monthly_insights(stats, None, [], [])

    assert insights["expense_count"] == 0
    assert insights["top_category"] is None
    assert insights["average_expense"] is None
    assert insights["largest_expense"] is None
    assert insights["budget_utilization"] is None
    assert insights["spending_change"]["percent"] is None
