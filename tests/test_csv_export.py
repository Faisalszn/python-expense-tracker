"""Exporting transactions as canonical Mizan CSV.

These parse the response with Python's own csv module rather than checking for
substrings: the promise is a file another program can read, so the tests read
it the way another program would.
"""

import csv
import io
from datetime import date

import pytest

from services.analytics import month_bounds
from tests.helpers import add_transaction, login, register

CANONICAL_HEADERS = ["date", "source", "amount", "type", "category"]


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def export(client, query=""):
    return client.get(f"/transactions/export.csv{query}")


def parse(response):
    """Decode and parse an export exactly as a spreadsheet or importer would."""
    text = response.data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_header_row_is_the_canonical_column_set(client):
    add_transaction(client)

    text = export(client).data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))

    assert next(reader) == CANONICAL_HEADERS


def test_file_starts_with_a_byte_order_mark(client):
    # Without it Excel reads the file in the host encoding and mangles any
    # non-ASCII source name.
    assert export(client).data.startswith(b"\xef\xbb\xbf")


def test_rows_carry_the_stored_values(client):
    add_transaction(
        client, date="2026-09-01", source="Carrefour", amount="420.00",
        type="expense", category="Groceries",
    )

    assert parse(export(client)) == [
        {
            "date": "2026-09-01",
            "source": "Carrefour",
            "amount": "420.00",
            "type": "expense",
            "category": "Groceries",
        }
    ]


def test_amounts_always_carry_two_decimal_places(client):
    add_transaction(client, amount="19.999", source="Rounded")
    add_transaction(client, amount="5", source="Whole")

    amounts = {row["source"]: row["amount"] for row in parse(export(client))}

    assert amounts["Rounded"] == "20.00"  # as stored, rounded by the column
    assert amounts["Whole"] == "5.00"


def test_no_internal_identifiers_are_exposed(client):
    add_transaction(client)

    rows = parse(export(client))

    assert list(rows[0]) == CANONICAL_HEADERS
    assert "id" not in rows[0]
    assert "user_id" not in rows[0]


def test_an_empty_result_still_produces_a_valid_file(client):
    response = export(client)

    assert response.status_code == 200
    assert parse(response) == []
    assert response.data.decode("utf-8-sig").splitlines()[0] == ",".join(CANONICAL_HEADERS)


# --- filters -----------------------------------------------------------------


def test_export_respects_the_search_filter(client):
    add_transaction(client, source="Carrefour")
    add_transaction(client, source="Amazon")

    sources = [row["source"] for row in parse(export(client, "?search=Carrefour"))]

    assert sources == ["Carrefour"]


def test_export_respects_the_category_filter(client):
    add_transaction(client, source="Groceries Txn", category="Groceries")
    add_transaction(client, source="Dining Txn", category="Dining")

    sources = [row["source"] for row in parse(export(client, "?category=Dining"))]

    assert sources == ["Dining Txn"]


def test_export_respects_the_type_filter(client):
    add_transaction(client, source="Paycheck", type="income", category="Salary")
    add_transaction(client, source="Shopping Trip", type="expense")

    sources = [row["source"] for row in parse(export(client, "?type=income"))]

    assert sources == ["Paycheck"]


def test_export_respects_several_filters_at_once(client):
    add_transaction(client, source="Carrefour Mall", category="Groceries", type="expense")
    add_transaction(client, source="Carrefour Online", category="Shopping", type="expense")
    add_transaction(client, source="Amazon", category="Shopping", type="expense")

    query = "?search=Carrefour&category=Shopping&type=expense"
    sources = [row["source"] for row in parse(export(client, query))]

    assert sources == ["Carrefour Online"]


def test_export_matches_the_rows_shown_on_the_transactions_page(client):
    add_transaction(client, source="Carrefour")
    add_transaction(client, source="Amazon")

    listed = client.get("/transactions?search=Amazon").data
    exported = parse(export(client, "?search=Amazon"))

    assert b"Amazon" in listed and b"Carrefour" not in listed
    assert [row["source"] for row in exported] == ["Amazon"]


# --- response shape ----------------------------------------------------------


def test_response_is_an_attachment_named_for_today(client):
    response = export(client)
    expected = f'attachment; filename="mizan-transactions-{date.today().isoformat()}.csv"'

    assert response.headers["Content-Disposition"] == expected


def test_response_declares_csv_and_utf8(client):
    assert export(client).headers["Content-Type"] == "text/csv; charset=utf-8"


# --- content that could break a CSV -----------------------------------------


def test_sources_containing_commas_and_quotes_survive(client):
    add_transaction(client, source='Cafe "Al Nakheel", Riyadh')

    rows = parse(export(client))

    assert rows[0]["source"] == 'Cafe "Al Nakheel", Riyadh'


def test_arabic_sources_survive(client):
    add_transaction(client, source="مركز التسوق")

    assert parse(export(client))[0]["source"] == "مركز التسوق"


# --- scope -------------------------------------------------------------------


def test_export_covers_every_month_not_just_the_current_one(client):
    # The dashboard summary is month-scoped; the export is not, and must not be.
    start, _ = month_bounds()
    add_transaction(client, date=start.replace(day=2).isoformat(), source="This Month")
    add_transaction(client, date="2026-01-15", source="Old One")

    sources = {row["source"] for row in parse(export(client))}

    assert sources == {"This Month", "Old One"}


def test_export_only_covers_the_logged_in_user(client):
    add_transaction(client, source="Alice Only")
    client.post("/logout")

    register(client, username="bob")
    add_transaction(client, source="Bob Only")

    assert [row["source"] for row in parse(export(client))] == ["Bob Only"]

    client.post("/logout")
    login(client)
    assert [row["source"] for row in parse(export(client))] == ["Alice Only"]


def test_export_requires_a_login(client):
    client.post("/logout")

    response = export(client)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
