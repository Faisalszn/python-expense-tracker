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
