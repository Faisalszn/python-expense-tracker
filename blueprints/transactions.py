from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, session

from blueprints.auth import login_required
from constants import CATEGORIES
from db import get_connection
from i18n import t

transactions_bp = Blueprint("transactions", __name__)


def validate_transaction_form(form):
    """Validate submitted form data, returning (data, error_key) tuple."""
    category = form.get("category", "").strip()
    date = form.get("date", "").strip()
    source = form.get("source", "").strip()
    amount_input = form.get("amount", "").strip()
    transaction_type = form.get("type", "").strip().lower()

    if category not in CATEGORIES:
        return None, "error.invalid_category"

    if not date:
        return None, "error.date_required"
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None, "error.invalid_date_format"

    if not source:
        return None, "error.source_required"
    if source.isdigit():
        return None, "error.source_numeric"

    try:
        amount = Decimal(amount_input)
    except InvalidOperation:
        return None, "error.amount_not_number"
    if not amount.is_finite():
        return None, "error.amount_not_number"
    if amount <= 0:
        return None, "error.amount_not_positive"

    if transaction_type not in ("income", "expense"):
        return None, "error.invalid_transaction_type"

    return {
        "date": date,
        "source": source,
        "amount": amount,
        "type": transaction_type,
        "category": category,
    }, None


def get_summary(user_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                "SELECT SUM(amount) FROM transactions WHERE type = 'income' AND user_id = %s",
                (user_id,)
            )
            total_income = cursor.fetchone()[0] or 0

            cursor.execute(
                "SELECT SUM(amount) FROM transactions WHERE type = 'expense' AND user_id = %s",
                (user_id,)
            )
            total_spending = cursor.fetchone()[0] or 0
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


def get_spending_by_category(user_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT category, SUM(amount) AS total
                FROM transactions
                WHERE type = 'expense' AND user_id = %s
                GROUP BY category
                ORDER BY total DESC
                """,
                (user_id,)
            )

            return cursor.fetchall()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return []


def get_monthly_spending(user_id):
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
