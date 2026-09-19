"""Uploading a CSV and previewing what it would import.

Nothing in this phase writes: every test here asserts both what the preview
says and — where it matters — that the database is untouched afterwards.
"""

import io
import re

import pytest

from services.analytics import month_bounds
from tests.helpers import add_transaction, login, register

HEADER = "date,source,amount,type,category"
VALID_ROW = "2026-09-01,Carrefour,420.00,expense,Groceries"


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def csv_file(text, filename="transactions.csv", encoding="utf-8"):
    data = text.encode(encoding) if isinstance(text, str) else text
    return {"file": (io.BytesIO(data), filename)}


def upload(client, text, filename="transactions.csv", encoding="utf-8"):
    return client.post(
        "/transactions/import/preview",
        data=csv_file(text, filename, encoding),
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def stored_sources(client):
    return client.get("/transactions").data


def preview_rows(response):
    """Parse the preview table into (status, error message) per row.

    Assertions have to read the table, not the page: the summary cards spell
    out "Invalid rows" and "Duplicates" whatever the counts are.
    """
    html = response.data.decode()
    body = html[html.index("<tbody>"):html.index("</tbody>")]

    rows = []
    for chunk in body.split("<tr")[1:]:
        status = re.search(r'class="preview-status status-(\w+)"', chunk).group(1)
        error = re.search(r'class="preview-error">(.*?)</span>', chunk, re.S)
        rows.append((status, error.group(1).strip() if error else None))
    return rows


def statuses(response):
    return [status for status, _ in preview_rows(response)]


def counts(response):
    """The three numbers the summary cards show."""
    html = response.data.decode()
    summary = html[html.index("preview-summary"):html.index("preview-note")]
    return [int(n) for n in re.findall(r"<bdi>(\d+)</bdi>", summary)]


# --- the happy path -----------------------------------------------------------


def test_upload_page_renders(client):
    response = client.get("/transactions/import")

    assert response.status_code == 200
    assert b"date,source,amount,type,category" in response.data  # the expected format


def test_valid_csv_previews_every_row(client):
    body = upload(client, f"{HEADER}\n{VALID_ROW}\n2026-09-02,Salary,12500.00,income,Salary").data

    assert b"Carrefour" in body
    assert b"Salary" in body
    assert b"Valid rows" in body


def test_preview_writes_nothing(client):
    # The central promise of this step.
    upload(client, f"{HEADER}\n{VALID_ROW}")

    assert b"Carrefour" not in stored_sources(client)


def test_preview_counts_valid_and_invalid_rows(client):
    text = "\n".join([
        HEADER,
        VALID_ROW,
        "2026-09-02,Salary,12500.00,income,Salary",
        "not-a-date,Broken,10.00,expense,Bills",
    ])

    valid, invalid, duplicate = counts(upload(client, text))

    assert (valid, invalid, duplicate) == (2, 1, 0)


def test_extra_columns_are_ignored(client):
    text = f"{HEADER},note\n{VALID_ROW},ignored\n"

    assert statuses(upload(client, text)) == ["valid"]


def test_headers_may_differ_in_case_and_spacing(client):
    text = f" Date , SOURCE ,Amount, Type ,CATEGORY\n{VALID_ROW}"

    response = upload(client, text)

    assert statuses(response) == ["valid"]
    assert b"Carrefour" in response.data


# --- whole-file rejections ----------------------------------------------------


def test_empty_file_rejected(client):
    response = upload(client, "")

    assert response.status_code == 400
    assert b"no transactions in it" in response.data


def test_header_only_file_rejected(client):
    response = upload(client, HEADER)

    assert response.status_code == 400
    assert b"no transactions in it" in response.data


@pytest.mark.parametrize("filename", ["transactions.txt", "transactions.xlsx", "transactions"])
def test_non_csv_extension_rejected(client, filename):
    response = upload(client, f"{HEADER}\n{VALID_ROW}", filename=filename)

    assert response.status_code == 400
    assert b"Only .csv files" in response.data


def test_csv_extension_is_matched_case_insensitively(client):
    response = upload(client, f"{HEADER}\n{VALID_ROW}", filename="Transactions.CSV")

    assert response.status_code == 200


def test_missing_file_rejected(client):
    response = client.post(
        "/transactions/import/preview", data={}, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert b"Choose a CSV file" in response.data


@pytest.mark.parametrize("missing", ["date", "source", "amount", "type", "category"])
def test_missing_required_header_rejected(client, missing):
    headers = [name for name in HEADER.split(",") if name != missing]
    response = upload(client, ",".join(headers) + "\nx,y,z,w")

    assert response.status_code == 400
    assert missing.encode() in response.data


def test_non_utf8_file_rejected(client):
    # A file Excel saved as Windows-1256 rather than UTF-8.
    response = upload(client, f"{HEADER}\n2026-09-01,مركز,10.00,expense,Bills", encoding="cp1256")

    assert response.status_code == 400
    assert b"not valid UTF-8" in response.data


def test_utf8_bom_is_accepted(client):
    # What Excel writes, and what Mizan's own export produces.
    response = upload(client, f"{HEADER}\n{VALID_ROW}", encoding="utf-8-sig")

    assert response.status_code == 200
    assert b"Carrefour" in response.data


def test_file_exceeding_the_row_limit_rejected(client):
    from services.csv_import import MAX_IMPORT_ROWS

    rows = "\n".join([VALID_ROW] * (MAX_IMPORT_ROWS + 1))
    response = upload(client, f"{HEADER}\n{rows}")

    assert response.status_code == 400
    assert str(MAX_IMPORT_ROWS).encode() in response.data


# --- row-level validation, shared with the Add/Edit forms ---------------------


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("31/12/2026,Shop,10.00,expense,Bills", "Invalid date format"),
        ("2026-13-40,Shop,10.00,expense,Bills", "Invalid date format"),
        ("2026-02-30,Shop,10.00,expense,Bills", "Invalid date format"),
        ("20260901,Shop,10.00,expense,Bills", "Invalid date format"),
        (",Shop,10.00,expense,Bills", "Date is required"),
        ("2026-09-01,Shop,-10.00,expense,Bills", "Amount must be greater than 0"),
        ("2026-09-01,Shop,0,expense,Bills", "Amount must be greater than 0"),
        ("2026-09-01,Shop,abc,expense,Bills", "Amount must be a number"),
        ("2026-09-01,Shop,NaN,expense,Bills", "Amount must be a number"),
        ('2026-09-01,Shop,"1,234.56",expense,Bills', "Amount must be a number"),
        ("2026-09-01,Shop,10.00,transfer,Bills", "Invalid transaction type"),
        ("2026-09-01,Shop,10.00,,Bills", "Invalid transaction type"),
        ("2026-09-01,Shop,10.00,expense,Crypto", "Invalid category"),
        ("2026-09-01,Shop,10.00,expense,", "Invalid category"),
        ("2026-09-01,,10.00,expense,Bills", "Source is required"),
        ("2026-09-01,12345,10.00,expense,Bills", "Source cannot be only numbers"),
    ],
)
def test_invalid_rows_are_reported_with_a_reason(client, row, message):
    # The same rules, and the same wording, the Add and Edit forms use.
    assert preview_rows(upload(client, f"{HEADER}\n{row}")) == [("invalid", message)]


def test_row_type_and_category_are_case_normalized(client):
    response = upload(client, f"{HEADER}\n2026-09-01,Shop,10.00,EXPENSE,groceries")

    assert statuses(response) == ["valid"]


def test_mixed_file_reports_each_row_separately(client):
    text = "\n".join([HEADER, VALID_ROW, "bad-date,Broken,10.00,expense,Bills"])

    response = upload(client, text)

    assert statuses(response) == ["valid", "invalid"]
    assert b"Carrefour" in response.data and b"Broken" in response.data


def test_invalid_row_values_are_escaped_not_executed(client):
    row = "2026-09-01,<script>alert(1)</script>,10.00,expense,Bills"
    body = upload(client, f"{HEADER}\n{row}").data

    assert b"<script>alert(1)</script>" not in body
    assert b"&lt;script&gt;" in body


# --- duplicates ---------------------------------------------------------------


def test_row_matching_a_stored_transaction_is_flagged(client):
    add_transaction(
        client, date="2026-09-01", source="Carrefour", amount="420.00",
        type="expense", category="Groceries",
    )

    assert preview_rows(upload(client, f"{HEADER}\n{VALID_ROW}")) == [
        ("duplicate", "Already recorded")
    ]


def test_duplicate_matching_ignores_case_and_spacing(client):
    add_transaction(
        client, date="2026-09-01", source="Carrefour  Mall", amount="420.00",
        type="expense", category="Groceries",
    )

    row = "2026-09-01,CARREFOUR Mall,420.00,expense,Groceries"
    assert statuses(upload(client, f"{HEADER}\n{row}")) == ["duplicate"]


def test_duplicate_matching_survives_amount_rounding(client):
    add_transaction(
        client, date="2026-09-01", source="Carrefour", amount="420.00",
        type="expense", category="Groceries",
    )

    # The column rounds 419.999 to 420.00, so the stored row is the same row.
    row = "2026-09-01,Carrefour,419.999,expense,Groceries"
    assert statuses(upload(client, f"{HEADER}\n{row}")) == ["duplicate"]


def test_repeated_row_within_one_file_is_flagged_once(client):
    response = upload(client, f"{HEADER}\n{VALID_ROW}\n{VALID_ROW}")

    # The first copy imports; only the repeat is flagged.
    assert statuses(response) == ["valid", "duplicate"]
    assert counts(response) == [1, 0, 1]


def test_a_different_transaction_is_not_a_duplicate(client):
    add_transaction(
        client, date="2026-09-01", source="Carrefour", amount="420.00",
        type="expense", category="Groceries",
    )

    # Same shop and day, different amount: a separate purchase.
    row = "2026-09-01,Carrefour,99.00,expense,Groceries"
    assert statuses(upload(client, f"{HEADER}\n{row}")) == ["valid"]


def test_another_users_transaction_is_never_a_duplicate(client):
    add_transaction(
        client, date="2026-09-01", source="Carrefour", amount="420.00",
        type="expense", category="Groceries",
    )
    client.post("/logout")

    register(client, username="bob")

    assert statuses(upload(client, f"{HEADER}\n{VALID_ROW}")) == ["valid"]


def test_duplicate_lookup_only_reads_the_dates_in_the_file(client, monkeypatch):
    add_transaction(client, date="2026-09-01", source="Carrefour", amount="420.00")

    seen = {}
    import blueprints.imports as imports_module

    original = imports_module.get_transactions_on_dates

    def spy(user_id, dates):
        seen["dates"] = list(dates)
        return original(user_id, dates)

    monkeypatch.setattr(imports_module, "get_transactions_on_dates", spy)
    upload(client, f"{HEADER}\n{VALID_ROW}")

    assert [d.isoformat() for d in seen["dates"]] == ["2026-09-01"]


# --- round trip with the exporter --------------------------------------------


def test_mizan_own_export_re_imports_as_all_duplicates(client):
    start, _ = month_bounds()
    add_transaction(client, date=start.replace(day=2).isoformat(), source="Carrefour")
    add_transaction(client, date="2026-01-15", source="Amazon", amount="75.25")

    exported = client.get("/transactions/export.csv").data

    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(exported), "mizan-export.csv")},
        content_type="multipart/form-data",
    )
    # Every row already exists, so nothing would be imported.
    assert statuses(response) == ["duplicate", "duplicate"]
    assert counts(response) == [0, 0, 2]


# --- access control -----------------------------------------------------------


def test_import_pages_require_a_login(client):
    client.post("/logout")

    assert client.get("/transactions/import").status_code == 302
    assert upload(client, f"{HEADER}\n{VALID_ROW}", ).request.path == "/login"


def test_preview_is_scoped_to_the_uploading_user(client):
    add_transaction(client, date="2026-09-01", source="Alice Only", amount="420.00")
    client.post("/logout")

    login(client)
    body = upload(client, f"{HEADER}\n{VALID_ROW}").data

    assert b"Alice Only" not in body


def test_unpadded_dates_are_accepted(client):
    # Pre-existing behaviour, shared with the Add/Edit forms: strptime accepts
    # an unpadded month or day, and the DATE column stores 2026-09-01 either
    # way. Rejecting it here would make the importer stricter than the form it
    # shares its rules with, for a row that stores correctly.
    row = "2026-9-1,Shop,10.00,expense,Bills"

    assert statuses(upload(client, f"{HEADER}\n{row}")) == ["valid"]


def test_unpadded_date_matches_a_stored_transaction(client):
    add_transaction(
        client, date="2026-09-01", source="Shop", amount="10.00",
        type="expense", category="Bills",
    )

    row = "2026-9-1,Shop,10.00,expense,Bills"
    assert statuses(upload(client, f"{HEADER}\n{row}")) == ["duplicate"]


def test_oversized_upload_is_refused_with_advice(client, app):
    limit = app.config["MAX_CONTENT_LENGTH"]
    oversized = b"x" * (limit + 1024)

    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(oversized), "huge.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert b"larger than 2 MB" in response.data


def test_row_numbers_point_at_the_line_in_the_file(client):
    text = "\n".join([HEADER, VALID_ROW, "bad,Broken,10.00,expense,Bills"])

    html = upload(client, text).data.decode()
    body = html[html.index("<tbody>"):html.index("</tbody>")]

    # Header is line 1, so the first transaction is line 2 — what a
    # spreadsheet shows when the user goes to correct the file.
    assert "<bdi>2</bdi>" in body
    assert "<bdi>3</bdi>" in body
