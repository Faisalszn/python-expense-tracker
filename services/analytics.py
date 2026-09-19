"""Date arithmetic behind Mizan's month-scoped figures.

The dashboard summary, the budget progress bars, and (from V13 on) the monthly
insights all have to agree on where "this month" starts and ends. Before this
module each of them worked that out for itself, which is how the dashboard
ended up reporting all-time totals while the budgets page reported monthly
ones. One definition, used by all of them, keeps them honest.

Ranges are half-open — `start <= date < end` — so a query can compare against
the DATE column directly and use an index on it, rather than formatting every
stored row with TO_CHAR before comparing strings.

Naive local dates throughout, matching the rest of the app and PostgreSQL's
TIMESTAMP WITHOUT TIME ZONE columns.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

_ONE_DECIMAL = Decimal("0.1")
_TWO_DECIMALS = Decimal("0.01")


def month_bounds(today=None):
    """Return the half-open [start, end) date range covering `today`'s month.

    Defaults to the current month. Pass `today` to scope a different one — and
    to keep tests independent of the calendar they happen to run on.
    """
    if today is None:
        today = date.today()

    start = today.replace(day=1)
    # Any day in the 29..31 range lands in the following month regardless of
    # its length, and day=1 snaps back to that month's first day. Avoids
    # special-casing December, February, and leap years separately.
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def spending_change(current_total, previous_total):
    """Compare this month's spending with last month's.

    `percent` is None when last month recorded no spending at all: every
    increase from zero is "up infinitely", which is arithmetic rather than
    information. The absolute delta is still reported, so the caller can say
    something true without it.
    """
    current_total = Decimal(current_total or 0)
    previous_total = Decimal(previous_total or 0)
    delta = current_total - previous_total

    if previous_total <= 0:
        percent = None
    else:
        percent = (delta / previous_total * 100).quantize(_ONE_DECIMAL, ROUND_HALF_UP)

    return {
        "current": current_total,
        "previous": previous_total,
        "delta": delta,
        "percent": percent,
        # Spending is the one figure here where up is the bad direction.
        "increased": delta > 0,
    }


def average_expense(total, count):
    """Mean size of one expense this month, or None if there were none."""
    if not count:
        return None
    return (Decimal(total or 0) / count).quantize(_TWO_DECIMALS, ROUND_HALF_UP)


def top_spending_category(spending_by_category):
    """The largest expense category this month, or None.

    Reads the first row of the breakdown the dashboard already fetched, which
    is ordered by total descending — no second query, and no re-sorting that
    could disagree with the list rendered right below it.
    """
    if not spending_by_category:
        return None

    category, total = spending_by_category[0]
    return {"category": category, "total": total}


def budget_utilization(budget_status):
    """Spending against limits across every category that has a budget.

    Returns None when no budgets are set: there is no ratio to report, and
    showing 0% would imply the user is comfortably inside a limit that does
    not exist.
    """
    if not budget_status:
        return None

    limit = sum((entry["limit"] for entry in budget_status), Decimal(0))
    spent = sum((entry["spent"] for entry in budget_status), Decimal(0))
    if limit <= 0:
        return None

    percent = (spent / limit * 100).quantize(_ONE_DECIMAL, ROUND_HALF_UP)
    return {
        "spent": spent,
        "limit": limit,
        "percent": percent,
        # The bar stops at full while the figure beside it tells the truth.
        "display_percent": min(percent, Decimal(100)),
        "over_budget": spent > limit,
    }


def monthly_insights(expense_stats, largest_expense, spending_by_category, budget_status):
    """Assemble the dashboard's five deterministic insights.

    Pure: every argument is already-fetched query output, so the whole panel
    can be tested without a database. Nothing here estimates, predicts, or
    infers — each figure is arithmetic over transactions the user entered.
    """
    return {
        "spending_change": spending_change(
            expense_stats["current_total"], expense_stats["previous_total"]
        ),
        "top_category": top_spending_category(spending_by_category),
        "average_expense": average_expense(
            expense_stats["current_total"], expense_stats["current_count"]
        ),
        "expense_count": expense_stats["current_count"],
        "largest_expense": largest_expense,
        "budget_utilization": budget_utilization(budget_status),
    }
