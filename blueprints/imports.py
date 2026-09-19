"""Importing transactions from a CSV file.

The route orchestrates and nothing more: reading the upload, asking
services.csv_import what the file would do, and rendering the answer. Parsing,
validation, and duplicate detection each live behind their own function, and
none of them can reach the database.

Nothing in this module writes. Uploading a file produces a preview and no
rows; importing them is a separate, explicit step.
"""

import psycopg2
from flask import Blueprint, flash, render_template, request, session

from blueprints.auth import login_required
from blueprints.transactions import get_transactions_on_dates
from constants import CATEGORIES
from i18n import t
from services.csv_import import MAX_IMPORT_ROWS, build_preview
from services.transaction_rules import canonical_key

imports_bp = Blueprint("imports", __name__)

CSV_EXTENSION = ".csv"


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

    user_id = session["user_id"]

    def existing_keys_for_dates(dates):
        stored = get_transactions_on_dates(user_id, dates)
        return {canonical_key(user_id, row) for row in stored}

    try:
        result = build_preview(uploaded.read(), user_id, existing_keys_for_dates)
    except psycopg2.Error as e:
        return upload_error("error.database", error=e)

    if result.file_error_key:
        return upload_error(result.file_error_key, detail=result.file_error_detail)

    return render_template(
        "import_preview.html",
        preview=result,
        filename=uploaded.filename,
    )
