import datetime

import pytest

from tests.helpers import add_transaction, register, set_budget


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def test_set_budget_creates_entry(client):
    response = set_budget(client, category="Groceries", monthly_limit="150")
    assert response.status_code == 200
    assert b"150.00" in client.get("/budgets").data


def test_set_budget_upserts_existing_category(client):
    set_budget(client, category="Groceries", monthly_limit="150")
    set_budget(client, category="Groceries", monthly_limit="300")
    body = client.get("/budgets").data
    assert b"300.00" in body
    assert b"150.00" not in body


def test_invalid_category_rejected(client):
    response = set_budget(client, category="NotACategory")
    assert b"Invalid category" in response.data
    assert b"NotACategory" not in client.get("/budgets").data


@pytest.mark.parametrize("bad_limit", ["NaN", "Infinity", "abc", ""])
def test_non_numeric_limit_rejected(client, bad_limit):
    set_budget(client, monthly_limit=bad_limit)
    assert b"200.00" not in client.get("/budgets").data


@pytest.mark.parametrize("non_positive", ["0", "-10"])
def test_non_positive_limit_rejected(client, non_positive):
    response = set_budget(client, monthly_limit=non_positive)
    assert b"greater than 0" in response.data


def test_budget_status_calculates_spent_and_remaining(client):
    set_budget(client, category="Groceries", monthly_limit="200")
    add_transaction(
        client, date="2026-01-01", category="Groceries", amount="50",
    )
    # January spending above should not count; only the current month should.
    today = datetime.date.today().isoformat()
    add_transaction(client, date=today, category="Groceries", amount="30")

    body = client.get("/budgets").data
    assert b"30.00" in body  # current month spend
    assert b"170.00" in body  # remaining = 200 - 30


def test_budget_over_limit_flagged(client):
    set_budget(client, category="Groceries", monthly_limit="10")
    today = datetime.date.today().isoformat()
    add_transaction(client, date=today, category="Groceries", amount="50")

    body = client.get("/budgets").data
    assert b"Over budget" in body


def test_delete_budget_removes_entry(client):
    set_budget(client, category="Groceries", monthly_limit="200")
    client.post("/budgets/Groceries/delete", follow_redirects=True)
    assert b"No budgets set yet" in client.get("/budgets").data
