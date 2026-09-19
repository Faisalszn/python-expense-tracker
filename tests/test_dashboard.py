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
from tests.helpers import add_transaction, login, register


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
