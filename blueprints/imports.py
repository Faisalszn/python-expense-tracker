"""Importing transactions from a CSV file.

The route orchestrates and nothing more: reading the upload, asking
services.csv_import what the file would do, and rendering the answer. Parsing,
validation, and duplicate detection each live behind their own function, and
none of them can reach the database.

Nothing in this module writes. Uploading a file produces a preview and no
rows; importing them is a separate, explicit step.
"""

import base64
import binascii
import hashlib

import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from psycopg2.extras import execute_values

from blueprints.auth import login_required
from blueprints.transactions import get_transactions_on_dates
from constants import CATEGORIES
from db import get_connection
from i18n import t
from services.csv_import import MAX_IMPORT_ROWS, build_preview
from services.transaction_rules import canonical_key

imports_bp = Blueprint("imports", __name__)

CSV_EXTENSION = ".csv"

# Enough of the offending line to recognise it, without storing whole rows of
# somebody's financial data in an error log.
RAW_ROW_LIMIT = 200

FILENAME_LIMIT = 255


def display_filename(raw):
    """Reduce an uploaded filename to something safe to store and show.

    This value is never used to build a path — the upload is read from memory
    and never written to disk — so the job here is only to drop directory
    components and anything unprintable, then bound the length. Jinja escapes
    it on the way out.

    Deliberately not werkzeug's secure_filename: that strips every non-ASCII
    character, which turns an Arabic filename into nothing useful. Mizan is a
    bilingual app, and mangling half its users' filenames to sanitise a string
    that never reaches a filesystem is a bad trade.
    """
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(character for character in name if character.isprintable()).strip()
    return name[:FILENAME_LIMIT] or "import.csv"


def find_previous_import(user_id, file_hash):
    """Return when this exact file was last imported, or None.

    Only a warning: a user who deleted those transactions may legitimately
    want to import the same file again. Row-level duplicate detection runs
    either way and is what actually protects the ledger.
    """
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT created_at
                FROM import_batches
                WHERE user_id = %s AND file_hash = %s AND status <> 'failed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, file_hash)
            )
            row = cursor.fetchone()
    except psycopg2.Error:
        # A missing warning must not block an import that is otherwise fine.
        return None

    return row[0] if row else None


def get_imports(user_id):
    """Return the user's imports, newest first.

    Not paginated: importing is an occasional act, so this list stays short
    for a personal ledger, and the (user_id, created_at DESC) index means
    reading it never gets more expensive than the rows it returns.
    """
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, filename, created_at, total_rows, successful_rows,
                       failed_rows, duplicate_rows, status
                FROM import_batches
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return []

    return [
        {
            "id": row[0],
            "filename": row[1],
            "created_at": row[2],
            "total_rows": row[3],
            "successful_rows": row[4],
            "failed_rows": row[5],
            "duplicate_rows": row[6],
            "status": row[7],
        }
        for row in rows
    ]


def get_import(import_id, user_id):
    """Return one import batch with its row errors, or None if not this user's."""
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, filename, created_at, total_rows, successful_rows,
                       failed_rows, duplicate_rows, status
                FROM import_batches
                WHERE id = %s AND user_id = %s
                """,
                (import_id, user_id)
            )
            batch = cursor.fetchone()
            if batch is None:
                return None

            cursor.execute(
                """
                SELECT row_number, error_key, raw_row
                FROM import_row_errors
                WHERE import_id = %s
                ORDER BY row_number
                """,
                (import_id,)
            )
            errors = cursor.fetchall()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return None

    return {
        "id": batch[0],
        "filename": batch[1],
        "created_at": batch[2],
        "total_rows": batch[3],
        "successful_rows": batch[4],
        "failed_rows": batch[5],
        "duplicate_rows": batch[6],
        "status": batch[7],
        "errors": [
            {"row_number": row[0], "error_key": row[1], "raw_row": row[2]} for row in errors
        ],
    }


def _insert_batch(cursor, user_id, filename, file_hash, counts, status):
    cursor.execute(
        """
        INSERT INTO import_batches
            (user_id, filename, file_hash, total_rows, successful_rows,
             failed_rows, duplicate_rows, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            user_id, filename, file_hash,
            counts["total"], counts["successful"], counts["failed"], counts["duplicate"],
            status,
        )
    )
    return cursor.fetchone()[0]


def record_import(user_id, filename, file_hash, preview, rows_to_import):
    """Write the batch, its transactions, and its row errors in one transaction.

    Either all of it lands or none of it does. A half-written batch would
    leave a history record claiming rows that are not there, which is worse
    than no record at all: it would have to be reconciled by hand.

    Returns the new import's id, or None if nothing was written.
    """
    counts = {
        "total": preview.total_count,
        "successful": len(rows_to_import),
        "failed": preview.invalid_count,
        "duplicate": preview.duplicate_count,
    }
    status = "completed" if preview.invalid_count == 0 else "partial"

    try:
        with get_connection() as connection:
            try:
                cursor = connection.cursor()
                import_id = _insert_batch(
                    cursor, user_id, filename, file_hash, counts, status
                )

                if rows_to_import:
                    execute_values(
                        cursor,
                        """
                        INSERT INTO transactions
                            (user_id, date, source, amount, type, category, import_id)
                        VALUES %s
                        """,
                        [
                            (
                                user_id,
                                row.normalized["date"],
                                row.normalized["source"],
                                row.normalized["amount"],
                                row.normalized["type"],
                                row.normalized["category"],
                                import_id,
                            )
                            for row in rows_to_import
                        ],
                    )

                failures = [
                    (
                        import_id,
                        row.number,
                        row.error_key,
                        ",".join(row.values.values())[:RAW_ROW_LIMIT],
                    )
                    for row in preview.rows
                    if row.status == "invalid"
                ]
                if failures:
                    execute_values(
                        cursor,
                        """
                        INSERT INTO import_row_errors
                            (import_id, row_number, error_key, raw_row)
                        VALUES %s
                        """,
                        failures,
                    )

                connection.commit()
                return import_id
            except psycopg2.Error:
                connection.rollback()
                raise
    except psycopg2.Error as e:
        flash(t("error.import_failed", error=e))
        record_failed_import(user_id, filename, file_hash, preview)
        return None


def record_failed_import(user_id, filename, file_hash, preview):
    """Note a rolled-back attempt, in its own transaction.

    Runs only after the batch above has provably rolled back, so it never
    claims rows that do not exist: successful_rows is zero, which is true.
    That keeps the invariant history depends on — a batch's successful_rows
    always equals the number of transactions actually stored from it — while
    still leaving the user evidence that the attempt happened.

    Best effort by design. If the database is unwell enough to have failed the
    import, it may fail this too, and an audit record that cannot be written
    must not become a second error in the user's face.
    """
    counts = {
        "total": preview.total_count,
        "successful": 0,
        "failed": preview.invalid_count,
        "duplicate": preview.duplicate_count,
    }

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            _insert_batch(cursor, user_id, filename, file_hash, counts, "failed")
            connection.commit()
    except psycopg2.Error:
        pass


def render_upload_form(**context):
    """Render the upload page. Shared with app.py's 413 handler."""
    return render_template(
        "import.html", max_rows=MAX_IMPORT_ROWS, categories=CATEGORIES, **context
    )


def upload_error(error_key, **kwargs):
    """Re-render the upload form with a message, rejecting the request."""
    flash(t(error_key, **kwargs))
    return render_upload_form(), 400


@imports_bp.route("/transactions/import")
@login_required
def upload():
    return render_upload_form()


def keys_already_stored(user_id):
    """A lookup of canonical keys already recorded on the given dates."""
    def lookup(dates):
        stored = get_transactions_on_dates(user_id, dates)
        return {canonical_key(user_id, row) for row in stored}

    return lookup


def evaluate_upload(raw_bytes, user_id):
    """Work out what `raw_bytes` would import.

    Returns (preview, error_response). Exactly one is ever set: a file that
    cannot be read at all is reported as a whole-file problem rather than as
    a page of broken rows.
    """
    try:
        result = build_preview(raw_bytes, user_id, keys_already_stored(user_id))
    except psycopg2.Error as e:
        return None, upload_error("error.database", error=e)

    if result.file_error_key:
        return None, upload_error(result.file_error_key, detail=result.file_error_detail)

    return result, None


def preview_page(result, raw_bytes, filename, user_id):
    """Render the preview. Called after any flash, never before.

    Rendering is separate from evaluating precisely so a message queued while
    deciding what to do still reaches the page it belongs on, instead of
    surfacing on whatever the user opens next.
    """
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    return render_template(
        "import_preview.html",
        preview=result,
        filename=filename,
        file_hash=file_hash,
        # The bytes travel back with the page so confirming re-runs the whole
        # pipeline over the same input, rather than trusting a classification
        # the browser has been holding. Base64 so no form encoding can alter a
        # single byte on the way.
        payload=base64.b64encode(raw_bytes).decode("ascii"),
        previously_imported_at=find_previous_import(user_id, file_hash),
    )


@imports_bp.route("/transactions/import/preview", methods=["POST"])
@login_required
def preview():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return upload_error("error.file_required")

    # The extension is a courtesy to the user, not a defence: the real check is
    # that the bytes only ever get decoded as UTF-8 and handed to a CSV reader.
    # The file is never written to disk and never executed.
    if not uploaded.filename.lower().endswith(CSV_EXTENSION):
        return upload_error("error.file_not_csv")

    # Kept for display only, never used to build a path.
    filename = display_filename(uploaded.filename)
    user_id = session["user_id"]
    raw_bytes = uploaded.read()

    result, error_response = evaluate_upload(raw_bytes, user_id)
    if error_response is not None:
        return error_response

    return preview_page(result, raw_bytes, filename, user_id)


@imports_bp.route("/transactions/import/confirm", methods=["POST"])
@login_required
def confirm():
    user_id = session["user_id"]
    filename = display_filename(request.form.get("filename", ""))
    include_duplicates = request.form.get("include_duplicates") == "yes"

    try:
        raw_bytes = base64.b64decode(request.form.get("payload", ""), validate=True)
    except (binascii.Error, ValueError):
        return upload_error("error.import_payload_unreadable")

    # Everything is checked again here, against the database as it is now.
    # The preview's verdict is a courtesy to the user, never an input we act
    # on: rows may have been imported by another tab since, and the payload
    # has been out of our hands.
    result, error_response = evaluate_upload(raw_bytes, user_id)
    if error_response is not None:
        return error_response

    rows_to_import = list(result.importable_rows)
    if include_duplicates:
        rows_to_import += [row for row in result.rows if row.status == "duplicate"]

    if not rows_to_import:
        flash(t("error.import_nothing_to_do"))
        return preview_page(result, raw_bytes, filename, user_id)

    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    import_id = record_import(user_id, filename, file_hash, result, rows_to_import)
    if import_id is None:
        # record_import has already explained why, and rolled everything back.
        return preview_page(result, raw_bytes, filename, user_id)

    flash(t("success.import_complete", count=len(rows_to_import)))
    return redirect(url_for("imports.detail", import_id=import_id))


@imports_bp.route("/transactions/imports")
@login_required
def history():
    return render_template("import_history.html", imports=get_imports(session["user_id"]))


@imports_bp.route("/transactions/imports/<int:import_id>")
@login_required
def detail(import_id):
    record = get_import(import_id, session["user_id"])
    # 404 rather than 403 for someone else's import: confirming that an id
    # exists would leak more than refusing to say anything about it.
    if record is None:
        return render_template("import_not_found.html"), 404

    return render_template("import_summary.html", record=record)
