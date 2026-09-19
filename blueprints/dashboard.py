from flask import Blueprint, render_template, session

from blueprints.auth import login_required
from blueprints.budgets import get_budget_status
from blueprints.transactions import (
    get_monthly_spending,
    get_spending_by_category,
    get_summary,
)
from i18n import t
from services.analytics import month_bounds

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def home():
    user_id = session["user_id"]

    # The headline figures cover the current month only. Earlier months are
    # never deleted or reset — they stay in the transactions list, the CSV
    # export, and the multi-month trend below, which is still whole-history.
    start, end = month_bounds()

    total_income, total_spending, net = get_summary(user_id, start, end)
    spending_by_category = get_spending_by_category(user_id, start, end)
    monthly_spending = get_monthly_spending(user_id)
    budget_status = get_budget_status(user_id)

    # Converted to float here only: Chart.js/tojson need plain JSON numbers,
    # while the Decimal values are kept everywhere else so money math stays exact.
    category_labels = [t("category." + row[0]) for row in spending_by_category]
    category_totals = [float(row[1]) for row in spending_by_category]

    monthly_labels = [row[0] for row in monthly_spending]
    monthly_totals = [float(row[1]) for row in monthly_spending]

    return render_template(
        "index.html",
        current_month=start.month,
        total_income=total_income,
        total_spending=total_spending,
        net=net,
        spending_by_category=spending_by_category,
        category_labels=category_labels,
        category_totals=category_totals,
        monthly_labels=monthly_labels,
        monthly_totals=monthly_totals,
        budget_status=budget_status
    )
