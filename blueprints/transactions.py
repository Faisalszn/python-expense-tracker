import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, session

from blueprints.auth import login_required
from constants import CATEGORIES
from db import get_connection
from i18n import t
from services.transaction_rules import TRANSACTION_FIELDS, normalize_and_validate

transactions_bp = Blueprint("transactions", __name__)


def validate_transaction_form(form):
    """Validate submitted form data, returning (data, error_key) tuple."""
    # The rules themselves live in services.transaction_rules so that CSV
    # import validates transactions exactly the way these forms do.
    return normalize_and_validate({field: form.get(field, "") for field in TRANSACTION_FIELDS})


def get_summary(user_id, start, end):
    """Return (income, spending, net) for [start, end) — one month, typically.

    `net` is that window's income minus its spending, not an account balance:
    money from outside the window is not part of it.
    """
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            # One pass with FILTER rather than a query per type: the row set is
            # identical, so scanning it twice only doubles the work.
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(amount) FILTER (WHERE type = 'income'), 0),
                    COALESCE(SUM(amount) FILTER (WHERE type = 'expense'), 0)
                FROM transactions
                WHERE user_id = %s AND date >= %s AND date < %s
                """,
                (user_id, start, end)
            )
            total_income, total_spending = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        total_income = total_spending = 0

    return total_income, total_spending, total_income - total_spending


def get_transactions(user_id, search="", category="", transaction_type=""):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            conditions = ["user_id = %s"]
            params = [user_id]

            if search:
                conditions.append("source LIKE %s")
                params.append(f"%{search}%")

            if category:
                conditions.append("category = %s")
                params.append(category)

            if transaction_type:
                conditions.append("type = %s")
                params.append(transaction_type)

            query = (
                "SELECT id, date, source, amount, type, category "
                "FROM transactions "
                "WHERE " + " AND ".join(conditions) + " ORDER BY id"
            )

            cursor.execute(query, params)
            return cursor.fetchall()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return []


def get_transaction_by_id(transaction_id, user_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, date, source, amount, type, category "
                "FROM transactions "
                "WHERE id = %s AND user_id = %s",
                (transaction_id, user_id)
            )
            return cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return None


def get_spending_by_category(user_id, start, end):
    """Return (category, total) expense pairs for [start, end), largest first."""
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT category, SUM(amount) AS total
                FROM transactions
                WHERE type = 'expense'
                    AND user_id = %s
                    AND date >= %s
                    AND date < %s
                GROUP BY category
                ORDER BY total DESC
                """,
                (user_id, start, end)
            )

            return cursor.fetchall()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return []


def get_expense_stats(user_id, start, end, previous_start):
    """Return this month's expense total and count, plus last month's total.

    One query rather than three: the two months are adjacent, so a single scan
    of [previous_start, end) can split them with FILTER.
    """
    empty = {"current_total": 0, "current_count": 0, "previous_total": 0}

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(amount) FILTER (WHERE date >= %s), 0),
                    COUNT(*) FILTER (WHERE date >= %s),
                    COALESCE(SUM(amount) FILTER (WHERE date < %s), 0)
                FROM transactions
                WHERE type = 'expense'
                    AND user_id = %s
                    AND date >= %s
                    AND date < %s
                """,
                (start, start, start, user_id, previous_start, end)
            )
            current_total, current_count, previous_total = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return empty

    return {
        "current_total": current_total,
        "current_count": current_count,
        "previous_total": previous_total,
    }


def get_largest_expense(user_id, start, end):
    """Return the biggest single expense in [start, end), or None."""
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT source, date, amount
                FROM transactions
                WHERE type = 'expense'
                    AND user_id = %s
                    AND date >= %s
                    AND date < %s
                ORDER BY amount DESC, id
                LIMIT 1
                """,
                (user_id, start, end)
            )
            row = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return None

    if row is None:
        return None

    # Ties break on id so the same expense is named on every reload.
    return {"source": row[0], "date": row[1], "amount": row[2]}


def get_monthly_spending(user_id):
    """Return (YYYY-MM, total) expense pairs across the user's whole history.

    Deliberately not month-scoped: this is the multi-month trend, and the proof
    that scoping the summary to one month never discards anything.
    """
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TO_CHAR(date, 'YYYY-MM') AS month, SUM(amount) AS total
                FROM transactions
                WHERE type = 'expense' AND user_id = %s
                GROUP BY month
                ORDER BY month
                """,
                (user_id,)
            )

            return cursor.fetchall()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return []


@transactions_bp.route("/transactions")
@login_required
def index():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    transaction_type = request.args.get("type", "").strip()

    return render_template(
        "transactions.html",
        transactions=get_transactions(session["user_id"], search, category, transaction_type),
        search=search,
        category=category,
        transaction_type=transaction_type,
        categories=CATEGORIES
    )


@transactions_bp.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        data, error = validate_transaction_form(request.form)
        if error:
            flash(t(error))
            return render_template("add.html", categories=CATEGORIES), 400

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO transactions (user_id, date, source, amount, type, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (session["user_id"], data["date"], data["source"],
                     data["amount"], data["type"], data["category"])
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(t("error.database", error=e))
            return render_template("add.html", categories=CATEGORIES), 500

        return redirect("/")

    return render_template("add.html", categories=CATEGORIES)


@transactions_bp.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit(transaction_id):
    transaction = get_transaction_by_id(transaction_id, session["user_id"])
    if transaction is None:
        return "Transaction not found", 404

    if request.method == "POST":
        data, error = validate_transaction_form(request.form)
        if error:
            flash(t(error))
            return render_template(
                "edit.html",
                transaction=transaction,
                categories=CATEGORIES
            ), 400

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE transactions
                    SET date = %s, source = %s, amount = %s, type = %s, category = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (data["date"], data["source"], data["amount"], data["type"],
                     data["category"], transaction_id, session["user_id"])
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(t("error.database", error=e))
            return render_template(
                "edit.html",
                transaction=transaction,
                categories=CATEGORIES
            ), 500

        return redirect("/transactions")

    return render_template("edit.html", transaction=transaction, categories=CATEGORIES)


@transactions_bp.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete(transaction_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM transactions WHERE id = %s AND user_id = %s",
                (transaction_id, session["user_id"])
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))

    return redirect("/transactions")
