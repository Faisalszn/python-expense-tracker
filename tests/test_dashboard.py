"""The dashboard summary is scoped to the current month.

V13 changed the three headline figures from all-time totals to current-month
ones. Nothing is deleted when a month ends, so most of these tests check both
halves of that: the figure moved on, and the data is still there.

Dates are derived from today rather than hardcoded, so the suite doesn't start
failing the moment the calendar leaves the month someone wrote it in.
"""

import calendar
from datetime import timedelta

import pytest

from services.analytics import month_bounds
from tests.helpers import add_transaction, login, register, set_budget


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def current_month_day(day=5):
    start, _ = month_bounds()
    return start.replace(day=day).isoformat()


def previous_month_day(day=5):
    start, _ = month_bounds()
    return (start - timedelta(days=1)).replace(day=day).isoformat()


def summary_cards(body):
    """Just the three headline cards.

    Assertions have to be scoped to them: the panels further down the page are
    whole-history on purpose, so an amount being absent from the summary says
    nothing about whether it is absent from the page.
    """
    html = body.decode()
    return html[html.index('<div class="summary-grid">'):html.index('<div class="analytics-grid">')]


def insights_panel(body):
    """Just the insights tiles."""
    html = body.decode()
    return html[
        html.index('class="panel insights-section"'):html.index('<div class="analytics-grid">')
    ]


def tile(body, heading):
    """A single insight tile, found by the text of its heading."""
    articles = insights_panel(body).split("<article")
    matches = [a for a in articles if heading in a]
    assert len(matches) == 1, f"expected exactly one {heading!r} tile, got {len(matches)}"
    return matches[0]


def category_panel(body):
    """Just the spending-by-category panel."""
    html = body.decode()
    return html[
        html.index('class="panel analytics-section"'):html.index('class="panel budget-section"')
    ]


def test_summary_covers_the_current_month_only(client):
    add_transaction(client, date=previous_month_day(), amount="7777.00", type="income")
    add_transaction(client, date=previous_month_day(), amount="999.00", type="expense")
    add_transaction(client, date=current_month_day(), amount="1000.00", type="income")
    add_transaction(client, date=current_month_day(), amount="250.00", type="expense")

    cards = summary_cards(client.get("/").data)

    assert "1000.00" in cards      # this month's income
    assert "250.00" in cards       # this month's spending
    assert "750.00" in cards       # net = 1000 - 250
    assert "7777.00" not in cards  # last month's income excluded
    assert "999.00" not in cards   # last month's spending excluded
    assert "8777.00" not in cards  # and no all-time total anywhere


def test_summary_is_zero_when_the_month_has_no_transactions(client):
    add_transaction(client, date=previous_month_day(), amount="4321.00", type="income")

    cards = summary_cards(client.get("/").data)

    assert cards.count("0.00") == 3  # income, spending and net all read zero
    assert "4321.00" not in cards


def test_net_can_be_negative(client):
    add_transaction(client, date=current_month_day(), amount="100.00", type="income")
    add_transaction(client, date=current_month_day(), amount="175.00", type="expense")

    assert "-75.00" in summary_cards(client.get("/").data)


def test_spending_by_category_covers_the_current_month_only(client):
    add_transaction(
        client, date=previous_month_day(), amount="640.00", category="Transport", type="expense"
    )
    add_transaction(
        client, date=current_month_day(), amount="120.00", category="Dining", type="expense"
    )

    panel = category_panel(client.get("/").data)

    assert "Dining" in panel
    assert "120.00" in panel
    assert "Transport" not in panel
    assert "640.00" not in panel


def test_summary_headings_name_the_current_month(client):
    start, _ = month_bounds()
    month_name = calendar.month_name[start.month]

    cards = summary_cards(client.get("/").data)

    assert f"{month_name} Income" in cards
    assert f"{month_name} Spending" in cards
    assert f"{month_name} Net" in cards


def test_third_figure_is_not_called_a_balance(client):
    # It is one month's income minus that month's spending, not an account
    # balance, and labelling it "Balance" would misrepresent it.
    body = client.get("/").data

    assert b"Balance" not in body
    assert b"Total Income" not in body
    assert b"Total Spending" not in body


def test_month_rollover_moves_the_summary_on_without_deleting_anything(client, monkeypatch):
    add_transaction(
        client, date=current_month_day(), amount="1234.00", source="September Rent", type="expense"
    )
    this_month = month_bounds()[0].strftime("%Y-%m").encode()

    # Simulate the calendar advancing: next month's bounds, same stored data.
    start, end = month_bounds()
    next_start, next_end = month_bounds(end)
    monkeypatch.setattr(
        "blueprints.dashboard.month_bounds", lambda today=None: (next_start, next_end)
    )

    body = client.get("/").data

    # The headline figures have moved on...
    assert "1234.00" not in summary_cards(body)
    assert summary_cards(body).count("0.00") == 3
    # ...but the transaction is still stored, still charted, still listed.
    assert this_month in body                                  # multi-month trend
    assert b"1234.00" in body                                  # and its amount
    assert b"September Rent" in client.get("/transactions").data


def test_historical_months_remain_in_the_monthly_trend(client):
    add_transaction(client, date=previous_month_day(), amount="310.00", type="expense")
    add_transaction(client, date=current_month_day(), amount="120.00", type="expense")

    start, _ = month_bounds()
    previous_label = (start - timedelta(days=1)).strftime("%Y-%m").encode()

    body = client.get("/").data

    # The trend chart is whole-history on purpose: it is what proves scoping
    # the summary to one month discards nothing.
    assert previous_label in body
    assert start.strftime("%Y-%m").encode() in body
    assert b"310.00" in body  # present in the trend's data table, not the summary


def test_summary_is_scoped_to_the_logged_in_user(client):
    add_transaction(client, date=current_month_day(), amount="5150.00", type="income")
    client.post("/logout")

    register(client, username="bob")
    cards = summary_cards(client.get("/").data)

    assert "5150.00" not in cards
    assert cards.count("0.00") == 3

    client.post("/logout")
    login(client)
    assert "5150.00" in summary_cards(client.get("/").data)


# --- deterministic monthly insights ------------------------------------------


def test_insights_report_top_category_average_and_largest_expense(client):
    add_transaction(
        client, date=current_month_day(), amount="300.00", category="Bills", source="Rent",
        type="expense",
    )
    add_transaction(
        client, date=current_month_day(), amount="60.00", category="Dining", source="Cafe",
        type="expense",
    )

    panel = insights_panel(client.get("/").data)

    assert "Bills" in panel            # top category, largest total
    assert "300.00" in panel           # and the largest single expense
    assert "Rent" in panel             # named, so it is identifiable
    assert "180.00" in panel           # average of 300 and 60


def test_insights_mark_rising_spending_as_up(client):
    add_transaction(client, date=previous_month_day(), amount="100.00", type="expense")
    add_transaction(client, date=current_month_day(), amount="150.00", type="expense")

    panel = insights_panel(client.get("/").data)

    # Direction is carried by the arrow and the word, not by colour alone.
    assert "spending-up" in panel
    assert "up" in panel
    assert "50.00" in panel   # the absolute change
    assert "50.0%" in panel   # and the proportional one


def test_insights_mark_falling_spending_as_down(client):
    add_transaction(client, date=previous_month_day(), amount="200.00", type="expense")
    add_transaction(client, date=current_month_day(), amount="150.00", type="expense")

    panel = insights_panel(client.get("/").data)

    assert "spending-down" in panel
    assert "down" in panel
    assert "25.0%" in panel


def test_insights_withhold_a_percentage_without_a_baseline(client):
    # Rising from zero is not "up 100%", and the panel must not imply it is.
    add_transaction(client, date=current_month_day(), amount="150.00", type="expense")

    change_tile = tile(client.get("/").data, "Spending vs")

    assert "to compare against" in change_tile
    assert "%" not in change_tile  # no percentage is claimed at all
    assert "150.00" in change_tile  # but the absolute change is still reported


def test_insights_report_no_expenses_for_an_empty_month(client):
    add_transaction(client, date=previous_month_day(), amount="500.00", type="expense")

    body = client.get("/").data
    panel = insights_panel(body)

    assert panel.count("No expenses this month") == 3  # top, average, largest

    # The spending-change tile still has something true to say: spending fell
    # by last month's whole total.
    change_tile = tile(body, "Spending vs")
    assert "spending-down" in change_tile
    assert "500.00" in change_tile
    assert "100.0%" in change_tile


def test_budget_utilization_appears_once_a_budget_is_set(client):
    panel = insights_panel(client.get("/").data)
    assert "No budgets set" in panel

    set_budget(client, category="Groceries", monthly_limit="400")
    add_transaction(
        client, date=current_month_day(), amount="100.00", category="Groceries", type="expense"
    )

    panel = insights_panel(client.get("/").data)
    assert "25%" in panel
    assert "400.00" in panel


def test_budget_utilization_can_exceed_the_limit(client):
    set_budget(client, category="Dining", monthly_limit="100")
    add_transaction(
        client, date=current_month_day(), amount="175.00", category="Dining", type="expense"
    )

    panel = insights_panel(client.get("/").data)

    assert "175%" in panel        # the figure is honest
    assert "width: 100%" in panel  # the bar stops at full
    assert "budget-over" in panel


def test_largest_expense_breaks_ties_stably(client):
    add_transaction(
        client, date=current_month_day(), amount="90.00", source="First Equal", type="expense"
    )
    add_transaction(
        client, date=current_month_day(), amount="90.00", source="Second Equal", type="expense"
    )

    # Same amount twice: the older row wins, on every reload.
    assert "First Equal" in insights_panel(client.get("/").data)
    assert "First Equal" in insights_panel(client.get("/").data)


def test_insights_only_count_expenses_not_income(client):
    add_transaction(client, date=current_month_day(), amount="9000.00", type="income")
    add_transaction(client, date=current_month_day(), amount="40.00", type="expense")

    panel = insights_panel(client.get("/").data)

    assert "9000.00" not in panel
    assert "40.00" in panel


def test_insights_are_scoped_to_the_logged_in_user(client):
    add_transaction(
        client, date=current_month_day(), amount="777.00", source="Alice Only", type="expense"
    )
    client.post("/logout")

    register(client, username="bob")
    panel = insights_panel(client.get("/").data)

    assert "777.00" not in panel
    assert "Alice Only" not in panel
