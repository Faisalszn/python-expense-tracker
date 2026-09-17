from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, session

from blueprints.auth import login_required
from constants import CATEGORIES
from db import get_connection
from i18n import t

budgets_bp = Blueprint("budgets", __name__)


def get_budget_status(user_id):
    """Return each budget's monthly limit alongside spending for the current month."""
    current_month = datetime.now().strftime("%Y-%m")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT category, monthly_limit
                FROM budgets
                WHERE user_id = %s
                ORDER BY category
                """,
                (user_id,)
            )
            budget_limits = cursor.fetchall()

            cursor.execute(
                """
                SELECT category, SUM(amount)
                FROM transactions
                WHERE type = 'expense'
                    AND user_id = %s
                    AND TO_CHAR(date, 'YYYY-MM') = %s
                GROUP BY category
                """,
                (user_id, current_month)
            )
            spending_by_category = dict(cursor.fetchall())
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return []

    status = []
    for category, limit in budget_limits:
        spent = spending_by_category.get(category, 0)
        percentage = (spent / limit) * 100

        status.append({
            "category": category,
            "limit": limit,
            "spent": spent,
            "remaining": limit - spent,
            "percentage": percentage,
            "display_percentage": min(percentage, 100),
            "over_budget": spent > limit,
        })

    return status


@budgets_bp.route("/budgets", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        limit_input = request.form.get("monthly_limit", "").strip()

        if category not in CATEGORIES:
            flash(t("error.invalid_category"))
            return redirect("/budgets")

        try:
            monthly_limit = Decimal(limit_input)
        except InvalidOperation:
            flash(t("error.monthly_limit_not_number"))
            return redirect("/budgets")

        if not monthly_limit.is_finite():
            flash(t("error.monthly_limit_not_number"))
            return redirect("/budgets")

        if monthly_limit <= 0:
            flash(t("error.monthly_limit_not_positive"))
            return redirect("/budgets")

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO budgets (user_id, category, monthly_limit)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, category)
                    DO UPDATE SET monthly_limit = excluded.monthly_limit
                    """,
                    (session["user_id"], category, monthly_limit)
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(t("error.database", error=e))

        return redirect("/budgets")

    return render_template(
        "budgets.html",
        budget_status=get_budget_status(session["user_id"]),
        categories=CATEGORIES
    )


@budgets_bp.route("/budgets/<category>/delete", methods=["POST"])
@login_required
def delete(category):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM budgets WHERE category = %s AND user_id = %s",
                (category, session["user_id"])
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))

    return redirect("/budgets")
