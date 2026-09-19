"""Confirming an import: the step that actually writes.

The rollback tests matter most here. A half-written batch would leave history
claiming rows that are not in the database, which has to be reconciled by
hand — so "nothing was written" is asserted against the tables themselves,
not inferred from a status code.
"""

import io
import re

import psycopg2
import pytest

import db
from tests.helpers import add_transaction, login, register

HEADER = "date,source,amount,type,category"
ROW_A = "2026-09-01,Carrefour,420.00,expense,Groceries"
ROW_B = "2026-09-02,Salary,12500.00,income,Salary"
BAD_ROW = "not-a-date,Broken,10.00,expense,Bills"


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def preview(client, text, filename="september.csv"):
    return client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(text.encode()), filename)},
        content_type="multipart/form-data",
    )


def confirm_fields(response):
    """The hidden payload the preview page hands back for confirmation."""
    html = response.data.decode()
    return {
        "payload": re.search(r'name="payload" value="([^"]*)"', html).group(1),
        "filename": re.search(r'name="filename" value="([^"]*)"', html).group(1),
    }


def import_csv(client, text, filename="september.csv", include_duplicates=False):
    """Run the whole flow: upload, preview, confirm."""
    fields = confirm_fields(preview(client, text, filename))
    if include_duplicates:
        fields["include_duplicates"] = "yes"
    return client.post("/transactions/import/confirm", data=fields, follow_redirects=True)


def count(table, **where):
    clause = " AND ".join(f"{column} = %s" for column in where) or "TRUE"
    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(f"SELECT count(*) FROM {table} WHERE {clause}", tuple(where.values()))
        return cursor.fetchone()[0]


def batch_row():
    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT total_rows, successful_rows, failed_rows, duplicate_rows, status, filename "
            "FROM import_batches ORDER BY id DESC LIMIT 1"
        )
        return cursor.fetchone()


# --- the happy path -----------------------------------------------------------


def test_confirming_imports_the_valid_rows(client):
    response = import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}")

    assert response.status_code == 200
    assert b"Import Complete" in response.data

    listed = client.get("/transactions").data
    assert b"Carrefour" in listed and b"Salary" in listed
    assert count("transactions") == 2


def test_imported_rows_keep_their_values(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")

    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT date, source, amount, type, category FROM transactions")
        date, source, amount, kind, category = cursor.fetchone()

    assert date.isoformat() == "2026-09-01"
    assert source == "Carrefour"
    assert str(amount) == "420.00"
    assert (kind, category) == ("expense", "Groceries")


def test_import_records_its_history(client):
    import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}", filename="september.csv")

    total, successful, failed, duplicates, status, filename = batch_row()

    assert (total, successful, failed, duplicates) == (2, 2, 0, 0)
    assert status == "completed"
    assert filename == "september.csv"


def test_imported_transactions_point_at_their_import(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")

    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT t.import_id, b.id FROM transactions t, import_batches b")
        import_id, batch_id = cursor.fetchone()

    assert import_id == batch_id


def test_manually_added_transactions_have_no_import(client):
    add_transaction(client, source="By Hand")

    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT import_id FROM transactions WHERE source = 'By Hand'")
        assert cursor.fetchone()[0] is None


# --- partial imports ----------------------------------------------------------


def test_valid_rows_import_even_when_others_are_invalid(client):
    import_csv(client, f"{HEADER}\n{ROW_A}\n{BAD_ROW}\n{ROW_B}")

    assert count("transactions") == 2
    assert b"Broken" not in client.get("/transactions").data

    total, successful, failed, duplicates, status, _ = batch_row()
    assert (total, successful, failed, duplicates, status) == (3, 2, 1, 0, "partial")


def test_skipped_rows_are_recorded_with_their_reason(client):
    import_csv(client, f"{HEADER}\n{ROW_A}\n{BAD_ROW}")

    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT row_number, error_key, raw_row FROM import_row_errors")
        row_number, error_key, raw_row = cursor.fetchone()

    assert row_number == 3  # header is line 1
    assert error_key == "error.invalid_date_format"
    assert "Broken" in raw_row


def test_the_summary_explains_each_skipped_row(client):
    response = import_csv(client, f"{HEADER}\n{ROW_A}\n{BAD_ROW}")

    assert b"Rows that were not imported" in response.data
    assert b"Invalid date format" in response.data


def test_a_file_with_no_usable_rows_imports_nothing(client):
    response = import_csv(client, f"{HEADER}\n{BAD_ROW}")

    assert b"nothing to import" in response.data
    assert count("transactions") == 0
    assert count("import_batches") == 0


# --- duplicates ---------------------------------------------------------------


def test_duplicates_are_skipped_by_default(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")
    import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}")

    # Only the new row is added the second time.
    assert count("transactions") == 2

    total, successful, failed, duplicates, status, _ = batch_row()
    assert (total, successful, failed, duplicates, status) == (2, 1, 0, 1, "completed")


def test_re_importing_the_same_file_changes_nothing(client):
    import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}")
    assert count("transactions") == 2

    response = import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}")

    assert count("transactions") == 2  # the whole point
    assert b"nothing to import" in response.data


def test_the_same_file_twice_is_warned_about(client):
    import_csv(client, f"{HEADER}\n{ROW_A}", filename="september.csv")

    body = preview(client, f"{HEADER}\n{ROW_A}", filename="september.csv").data

    assert b"imported this same file before" in body


def test_duplicates_import_when_explicitly_chosen(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")
    import_csv(client, f"{HEADER}\n{ROW_A}", include_duplicates=True)

    # Two identical coffees on one day are a real thing to record.
    assert count("transactions") == 2


def test_choosing_to_import_duplicates_is_recorded(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")
    import_csv(client, f"{HEADER}\n{ROW_A}", include_duplicates=True)

    total, successful, failed, duplicates, _, _ = batch_row()
    assert (total, successful, failed, duplicates) == (1, 1, 0, 1)


def test_duplicates_are_re_checked_at_confirm_time(client):
    # The preview said "valid"; the row is imported by another route before
    # the user confirms. The confirm step must notice.
    fields = confirm_fields(preview(client, f"{HEADER}\n{ROW_A}"))
    add_transaction(
        client, date="2026-09-01", source="Carrefour", amount="420.00",
        type="expense", category="Groceries",
    )

    client.post("/transactions/import/confirm", data=fields, follow_redirects=True)

    assert count("transactions") == 1  # not imported a second time


# --- atomicity ----------------------------------------------------------------


def test_batch_rolls_back_entirely_when_the_database_fails(client, monkeypatch):
    import blueprints.imports as imports_module

    real_execute_values = imports_module.execute_values
    calls = {"n": 0}

    def fail_on_the_transactions_insert(cursor, sql, argslist, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise psycopg2.OperationalError("connection lost mid-batch")
        return real_execute_values(cursor, sql, argslist, *args, **kwargs)

    monkeypatch.setattr(imports_module, "execute_values", fail_on_the_transactions_insert)

    response = import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}")

    # Not one row, and no batch record claiming otherwise.
    assert count("transactions") == 0
    assert count("import_row_errors") == 0
    assert count("import_batches", status="completed") == 0
    assert count("import_batches", status="partial") == 0
    assert b"nothing was imported" in response.data


def test_a_failed_batch_is_still_visible_in_history(client, monkeypatch):
    import blueprints.imports as imports_module

    def always_fail(*args, **kwargs):
        raise psycopg2.OperationalError("connection lost mid-batch")

    monkeypatch.setattr(imports_module, "execute_values", always_fail)
    import_csv(client, f"{HEADER}\n{ROW_A}\n{ROW_B}")

    total, successful, failed, duplicates, status, _ = batch_row()

    # The attempt is recorded, and it claims nothing that is not true.
    assert status == "failed"
    assert successful == 0
    assert total == 2
    assert count("transactions") == 0


def test_an_unwritable_audit_record_does_not_break_the_page(client, monkeypatch):
    # If the database is unwell enough to fail the import, it may fail the
    # note about the failure too. That must not become a second error.
    import blueprints.imports as imports_module

    def always_fail(*args, **kwargs):
        raise psycopg2.OperationalError("database is down")

    monkeypatch.setattr(imports_module, "execute_values", always_fail)
    monkeypatch.setattr(imports_module, "_insert_batch", always_fail)

    response = import_csv(client, f"{HEADER}\n{ROW_A}")

    assert response.status_code == 200
    assert count("transactions") == 0
    assert count("import_batches") == 0


# --- the payload is never trusted --------------------------------------------


def test_a_tampered_payload_is_revalidated_not_believed(client):
    fields = confirm_fields(preview(client, f"{HEADER}\n{ROW_A}"))

    import base64
    tampered = f"{HEADER}\n2026-09-01,Injected,-999.00,expense,Groceries"
    fields["payload"] = base64.b64encode(tampered.encode()).decode()

    response = client.post("/transactions/import/confirm", data=fields, follow_redirects=True)

    # Re-validated from scratch: a negative amount is rejected here too.
    assert count("transactions") == 0
    assert b"Injected" not in client.get("/transactions").data
    assert b"greater than 0" in response.data


def test_an_unreadable_payload_is_refused(client):
    response = client.post(
        "/transactions/import/confirm",
        data={"payload": "not-base64!!", "filename": "x.csv"},
        follow_redirects=True,
    )

    assert response.status_code == 400
    assert count("transactions") == 0


def test_a_missing_payload_is_refused(client):
    response = client.post("/transactions/import/confirm", data={}, follow_redirects=True)

    assert response.status_code == 400
    assert count("transactions") == 0


# --- ownership ----------------------------------------------------------------


def test_an_import_lands_in_the_uploading_users_account(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")
    client.post("/logout")

    register(client, username="bob")
    assert b"Carrefour" not in client.get("/transactions").data
    assert count("transactions") == 1  # still only alice's


def test_another_users_import_summary_is_not_reachable(client):
    response = import_csv(client, f"{HEADER}\n{ROW_A}")
    import_id = re.search(r"/transactions/imports/(\d+)", response.request.path).group(1)
    client.post("/logout")

    register(client, username="bob")
    bobs_view = client.get(f"/transactions/imports/{import_id}")

    assert bobs_view.status_code == 404
    assert b"Carrefour" not in bobs_view.data


def test_a_missing_import_is_a_404(client):
    assert client.get("/transactions/imports/999999").status_code == 404


def test_confirming_requires_a_login(client):
    fields = confirm_fields(preview(client, f"{HEADER}\n{ROW_A}"))
    client.post("/logout")

    response = client.post("/transactions/import/confirm", data=fields)

    assert response.status_code == 302
    assert count("transactions") == 0


def test_the_summary_is_reachable_again_later(client):
    response = import_csv(client, f"{HEADER}\n{ROW_A}")
    import_id = re.search(r"/transactions/imports/(\d+)", response.request.path).group(1)

    client.post("/logout")
    login(client)

    assert client.get(f"/transactions/imports/{import_id}").status_code == 200


# --- discoverability ----------------------------------------------------------


def test_the_import_flow_is_reachable_from_the_ui(client):
    # The flow is complete now, so it is allowed to be discoverable.
    assert b"/transactions/import" in client.get("/").data              # navbar
    assert b"/transactions/import" in client.get("/transactions").data  # page button


# --- filenames ----------------------------------------------------------------


def test_a_non_ascii_filename_survives(client):
    # Mizan is bilingual; an Arabic filename must stay recognisable in history.
    import_csv(client, f"{HEADER}\n{ROW_A}", filename="ميزانية.csv")

    assert batch_row()[5] == "ميزانية.csv"


@pytest.mark.parametrize(
    ("uploaded", "stored"),
    [
        ("../../etc/passwd.csv", "passwd.csv"),
        (r"C:\Users\me\september.csv", "september.csv"),
        ("plain.csv", "plain.csv"),
    ],
)
def test_directory_components_are_stripped_from_filenames(client, uploaded, stored):
    # The value is only ever displayed, but it should not look like a path.
    from blueprints.imports import display_filename

    assert display_filename(uploaded) == stored


def test_control_characters_are_stripped_from_filenames(client):
    from blueprints.imports import display_filename

    assert display_filename("sep\x00tem\nber.csv") == "september.csv"


def test_an_empty_filename_falls_back(client):
    from blueprints.imports import display_filename

    assert display_filename("") == "import.csv"
    assert display_filename(None) == "import.csv"


def test_a_very_long_filename_is_bounded(client):
    from blueprints.imports import FILENAME_LIMIT, display_filename

    assert len(display_filename("a" * 1000 + ".csv")) == FILENAME_LIMIT
