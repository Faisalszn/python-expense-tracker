"""The import-history schema.

Phase 6 adds tables and no application code, so these exercise the database
directly: the constraints and cascades are the deliverable, and the point of
declaring them is that they hold even when a future bug in the application
would otherwise write something incoherent.
"""

import psycopg2
import pytest

import db


@pytest.fixture()
def cursor():
    with db.get_connection() as connection:
        yield connection.cursor(), connection


def make_user(cursor, username="alice"):
    cur, connection = cursor
    cur.execute(
        "INSERT INTO users (username, password_hash) VALUES (%s, 'x') RETURNING id",
        (username,),
    )
    user_id = cur.fetchone()[0]
    connection.commit()
    return user_id


def make_batch(cursor, user_id, status="completed", total=3, ok=3, failed=0, duplicates=0):
    cur, connection = cursor
    cur.execute(
        """
        INSERT INTO import_batches
            (user_id, filename, file_hash, total_rows, successful_rows,
             failed_rows, duplicate_rows, status)
        VALUES (%s, 'september.csv', 'abc123', %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, total, ok, failed, duplicates, status),
    )
    batch_id = cur.fetchone()[0]
    connection.commit()
    return batch_id


def make_transaction(cursor, user_id, import_id=None, source="Carrefour"):
    cur, connection = cursor
    cur.execute(
        """
        INSERT INTO transactions (user_id, date, source, amount, type, category, import_id)
        VALUES (%s, '2026-09-01', %s, 10.00, 'expense', 'Groceries', %s)
        RETURNING id
        """,
        (user_id, source, import_id),
    )
    transaction_id = cur.fetchone()[0]
    connection.commit()
    return transaction_id


# --- the migration itself -----------------------------------------------------


def test_migration_is_recorded(cursor):
    cur, _ = cursor
    cur.execute(
        "SELECT version FROM schema_migrations WHERE version = %s", ("0004_import_history",)
    )

    assert cur.fetchone() is not None


def test_migration_is_idempotent():
    # Every migration file has to be safe against a database that already has
    # its objects; run_migrations skips recorded ones, but the SQL itself must
    # not depend on that.
    db.run_migrations()
    db.run_migrations()


@pytest.mark.parametrize(
    "index",
    [
        "import_batches_user_created_idx",
        "import_batches_user_hash_idx",
        "import_row_errors_import_idx",
        "transactions_import_idx",
    ],
)
def test_expected_indexes_exist(cursor, index):
    cur, _ = cursor
    cur.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s", (index,))

    assert cur.fetchone() is not None


def test_batch_defaults_fill_themselves_in(cursor):
    cur, connection = cursor
    user_id = make_user(cursor)

    cur.execute(
        """
        INSERT INTO import_batches
            (user_id, filename, file_hash, total_rows, successful_rows, failed_rows, status)
        VALUES (%s, 'f.csv', 'h', 1, 1, 0, 'completed')
        RETURNING created_at, duplicate_rows
        """,
        (user_id,),
    )
    created_at, duplicate_rows = cur.fetchone()
    connection.commit()

    assert created_at is not None
    assert duplicate_rows == 0


# --- constraints --------------------------------------------------------------


@pytest.mark.parametrize("status", ["completed", "partial", "failed"])
def test_every_intended_status_is_accepted(cursor, status):
    assert make_batch(cursor, make_user(cursor), status=status)


@pytest.mark.parametrize("status", ["pending", "success", "", "COMPLETED"])
def test_unknown_status_is_rejected(cursor, status):
    user_id = make_user(cursor)

    with pytest.raises(psycopg2.errors.CheckViolation):
        make_batch(cursor, user_id, status=status)


@pytest.mark.parametrize(
    ("total", "ok", "failed", "duplicates"),
    [(-1, 0, 0, 0), (1, -1, 0, 0), (1, 0, -1, 0), (1, 0, 0, -1)],
)
def test_negative_counts_are_rejected(cursor, total, ok, failed, duplicates):
    user_id = make_user(cursor)

    with pytest.raises(psycopg2.errors.CheckViolation):
        make_batch(cursor, user_id, total=total, ok=ok, failed=failed, duplicates=duplicates)


def test_counts_cannot_exceed_the_rows_the_file_held(cursor):
    user_id = make_user(cursor)

    with pytest.raises(psycopg2.errors.CheckViolation):
        make_batch(cursor, user_id, total=5, ok=4, failed=2)


def test_skipped_duplicates_leave_the_counts_consistent(cursor):
    # 10 rows: 7 imported, 1 invalid, 2 skipped as duplicates.
    assert make_batch(cursor, make_user(cursor), total=10, ok=7, failed=1, duplicates=2)


def test_a_batch_must_belong_to_a_real_user(cursor):
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        make_batch(cursor, 999999)


def test_a_row_error_must_belong_to_a_real_batch(cursor):
    cur, _ = cursor

    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute(
            "INSERT INTO import_row_errors (import_id, row_number, error_key) "
            "VALUES (999999, 2, 'error.invalid_category')"
        )


# --- deletion behaviour -------------------------------------------------------


def test_deleting_an_import_keeps_its_transactions(cursor):
    # The invariant that matters most here: import history is a receipt, and
    # throwing away a receipt must never throw away the money it describes.
    cur, connection = cursor
    user_id = make_user(cursor)
    import_id = make_batch(cursor, user_id)
    transaction_id = make_transaction(cursor, user_id, import_id, source="Still Here")

    cur.execute("DELETE FROM import_batches WHERE id = %s", (import_id,))
    connection.commit()

    cur.execute("SELECT source, import_id FROM transactions WHERE id = %s", (transaction_id,))
    source, orphaned_import_id = cur.fetchone()

    assert source == "Still Here"
    assert orphaned_import_id is None  # it simply lost its provenance


def test_deleting_an_import_removes_its_row_errors(cursor):
    cur, connection = cursor
    user_id = make_user(cursor)
    import_id = make_batch(cursor, user_id, total=2, ok=1, failed=1)

    cur.execute(
        "INSERT INTO import_row_errors (import_id, row_number, error_key, raw_row) "
        "VALUES (%s, 3, 'error.invalid_date_format', 'bad,row,here')",
        (import_id,),
    )
    cur.execute("DELETE FROM import_batches WHERE id = %s", (import_id,))
    connection.commit()

    cur.execute("SELECT count(*) FROM import_row_errors WHERE import_id = %s", (import_id,))
    assert cur.fetchone()[0] == 0


def test_deleting_a_user_removes_their_import_history(cursor):
    cur, connection = cursor
    user_id = make_user(cursor)
    import_id = make_batch(cursor, user_id)
    cur.execute(
        "INSERT INTO import_row_errors (import_id, row_number, error_key) VALUES (%s, 2, 'k')",
        (import_id,),
    )
    connection.commit()

    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    connection.commit()

    cur.execute("SELECT count(*) FROM import_batches WHERE id = %s", (import_id,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM import_row_errors WHERE import_id = %s", (import_id,))
    assert cur.fetchone()[0] == 0


def test_one_users_import_cannot_be_reached_from_another(cursor):
    # Ownership lives on the batch, so every history query can scope on it.
    cur, _ = cursor
    alice = make_user(cursor, "alice")
    bob = make_user(cursor, "bob")
    alice_import = make_batch(cursor, alice)

    cur.execute(
        "SELECT count(*) FROM import_batches WHERE id = %s AND user_id = %s",
        (alice_import, bob),
    )
    assert cur.fetchone()[0] == 0


# --- transactions keep working without an import ------------------------------


def test_manually_added_transactions_have_no_import(cursor):
    cur, _ = cursor
    user_id = make_user(cursor)
    transaction_id = make_transaction(cursor, user_id)

    cur.execute("SELECT import_id FROM transactions WHERE id = %s", (transaction_id,))
    assert cur.fetchone()[0] is None


def test_the_new_column_does_not_disturb_existing_behaviour(client):
    # The app has no idea import_id exists yet; adding it must change nothing.
    from tests.helpers import add_transaction, register

    register(client)
    add_transaction(client, source="Unaffected")

    assert b"Unaffected" in client.get("/transactions").data
