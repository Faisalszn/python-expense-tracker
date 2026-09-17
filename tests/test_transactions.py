import re

import pytest

from tests.helpers import add_transaction, register


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


@pytest.mark.parametrize("bad_date", ["", "   ", "not-a-date", "2026-13-40"])
def test_invalid_dates_rejected_and_not_stored(client, bad_date):
    response = add_transaction(client, date=bad_date, source="Should Not Save")
    assert response.status_code == 400
    assert b"Should Not Save" not in client.get("/transactions").data


@pytest.mark.parametrize("bad_amount", ["NaN", "Infinity", "-Infinity", "sNaN", "abc", ""])
def test_invalid_amounts_rejected(client, bad_amount):
    response = add_transaction(client, amount=bad_amount)
    assert response.status_code == 400


@pytest.mark.parametrize("non_positive_amount", ["0", "-5"])
def test_non_positive_amounts_rejected(client, non_positive_amount):
    response = add_transaction(client, amount=non_positive_amount)
    assert response.status_code == 400
    assert b"greater than 0" in response.data


def test_precise_decimal_amount_rounds_correctly(client):
    add_transaction(client, amount="19.999")
    assert b"20.00" in client.get("/transactions").data


def test_numeric_only_source_rejected(client):
    response = add_transaction(client, source="12345")
    assert response.status_code == 400
    assert b"cannot be only numbers" in response.data


def test_invalid_category_rejected(client):
    response = add_transaction(client, category="NotACategory")
    assert response.status_code == 400


def test_valid_transaction_is_stored(client):
    response = add_transaction(client, source="Valid Store", amount="10.00")
    assert response.status_code == 200
    assert b"Valid Store" in client.get("/transactions").data


def test_edit_transaction_updates_fields(client):
    add_transaction(client, source="Original")
    match = re.search(rb"<td>(\d+)</td>", client.get("/transactions").data)
    transaction_id = match.group(1).decode()

    response = client.post(
        f"/transactions/{transaction_id}/edit",
        data={
            "date": "2026-09-05",
            "source": "Updated",
            "amount": "99.99",
            "type": "expense",
            "category": "Dining",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    body = client.get("/transactions").data
    assert b"Updated" in body
    assert b"Original" not in body


def test_delete_transaction_removes_row(client):
    add_transaction(client, source="Delete Me")
    match = re.search(rb"<td>(\d+)</td>", client.get("/transactions").data)
    transaction_id = match.group(1).decode()

    client.post(f"/transactions/{transaction_id}/delete", follow_redirects=True)
    assert b"Delete Me" not in client.get("/transactions").data


def test_filter_by_search_term(client):
    add_transaction(client, source="Carrefour")
    add_transaction(client, source="Amazon")
    body = client.get("/transactions?search=Carrefour").data
    assert b"Carrefour" in body
    assert b"Amazon" not in body


def test_filter_by_category(client):
    add_transaction(client, source="Groceries Txn", category="Groceries")
    add_transaction(client, source="Dining Txn", category="Dining")
    body = client.get("/transactions?category=Dining").data
    assert b"Dining Txn" in body
    assert b"Groceries Txn" not in body
