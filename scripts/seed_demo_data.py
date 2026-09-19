"""Create (or reset) a demo account with six months of realistic data.

Usage:
    python scripts/seed_demo_data.py

Safe to re-run any time, including right before a demo: it deletes any
existing account with the same username first (transactions, budgets and
import history all go with it via ON DELETE CASCADE), then rebuilds it, so
the demo always starts from the same known state.

Two things make the result presentable rather than merely present:

- Everything is anchored to calendar months rather than "days ago". The
  dashboard summary is month-scoped, so a fixed day offset would land in a
  different month depending on the day you run this, and could leave the
  current month looking empty on stage.
- The current month is filled only up to today. Nothing is dated in the
  future, which would be visible in the transactions list and would skew the
  month-to-date figures.

The data is random but seeded, so every run produces the same six months.

Uses the same DATABASE_URL / .env as the app itself (via db.py) — run this
with the same environment you run `python app.py` with.
"""

import random
import sys
from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path

from werkzeug.security import generate_password_hash

# Allows running this script directly (`python scripts/seed_demo_data.py`)
# without needing `python -m` or a PYTHONPATH tweak: put the project root
# (this file's parent directory) on sys.path so `db` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_connection  # noqa: E402

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "Demo12345!"

MONTHS_OF_HISTORY = 6

# Fixed so a rehearsal and the real presentation show identical numbers.
SEED = 1309

# Monthly salary, paid on the first. Later months are slightly higher: six
# months of identical income looks generated, and a small raise gives the
# month-over-month figures something true to say.
BASE_SALARY = Decimal("12500.00")
RAISE_AFTER_MONTHS = 3
RAISE_AMOUNT = Decimal("900.00")

RENT = Decimal("2800.00")

# (source, category, low, high, times per month)
REGULAR_SPENDING = [
    ("Carrefour", "Groceries", 180, 520, 3),
    ("Tamimi Markets", "Groceries", 90, 260, 2),
    ("Al Baik", "Dining", 28, 65, 3),
    ("Starbucks", "Dining", 18, 44, 4),
    ("Najd Village", "Dining", 120, 320, 1),
    ("Petromin Station", "Transport", 95, 145, 2),
    ("Careem", "Transport", 22, 68, 4),
    ("Jarir Bookstore", "Shopping", 60, 340, 1),
    ("Netflix", "Entertainment", 56, 56, 1),
    ("Fitness Time", "Entertainment", 199, 199, 1),
]

# Fixed monthly bills, charged on the same day each month.
FIXED_BILLS = [
    (3, "STC Internet", "Bills", Decimal("299.00")),
    (5, "Mobily Postpaid", "Bills", Decimal("140.00")),
    (9, "National Water Company", "Bills", Decimal("85.00")),
]

# Things that happen some months and not others. No calendar-specific labels:
# this script runs at any time of year, so an occasion named here would end up
# attached to the wrong month.
OCCASIONAL = [
    ("Car Maintenance", "Transport", 380, 950),
    ("IKEA", "Shopping", 250, 1400),
    ("Flight Tickets", "Transport", 700, 1900),
    ("Dentist", "Other", 300, 800),
    ("VOX Cinemas", "Entertainment", 70, 180),
    ("Extra Stores", "Shopping", 180, 900),
    ("Pharmacy", "Other", 45, 190),
    ("Boulevard Riyadh", "Entertainment", 120, 400),
    ("Steak House", "Dining", 180, 420),
    ("Lulu Hypermarket", "Groceries", 200, 460),
]

# Large one-offs, in (months_ago, source, category, amount, day) form. Real
# spending is fairly flat month to month, which is honest but makes for a
# featureless trend line on a slide; these give it the shape a real year has.
MAJOR_EXPENSES = [
    (4, "Annual Car Insurance", "Other", Decimal("3150.00"), 12),
    (3, "Family Trip - Flights & Hotel", "Transport", Decimal("5400.00"), 18),
    (1, "New Laptop", "Shopping", Decimal("4299.00"), 9),
]

# Extra income beyond salary, in (months_ago, source, amount) form.
EXTRA_INCOME = [
    (4, "Performance Bonus", Decimal("4200.00"), 14),
    (2, "Freelance Project", Decimal("2600.00"), 17),
    (0, "Freelance Project", Decimal("1800.00"), 11),
]


def month_start(today, months_ago):
    """First day of the month `months_ago` before the one containing `today`."""
    month_index = today.year * 12 + (today.month - 1) - months_ago
    return date(month_index // 12, month_index % 12 + 1, 1)


def electricity_for(day_in_month):
    """Saudi summer bills run far higher than winter ones.

    Keyed off the real calendar month, so it stays true whenever this runs.
    """
    if day_in_month.month in (6, 7, 8, 9):
        return Decimal(random.Random(day_in_month.toordinal()).randint(620, 980))
    return Decimal(random.Random(day_in_month.toordinal()).randint(180, 340))


def money(rng, low, high):
    """A plausible amount: rarely a round number, always two decimal places."""
    riyals = rng.randint(low, high)
    halalas = rng.choice([0, 0, 25, 50, 50, 75, 90, 95])
    return Decimal(f"{riyals}.{halalas:02d}")


def spending_day(rng, start, latest_day):
    """A day within the month, never past `latest_day`."""
    return start.replace(day=rng.randint(1, latest_day))


def build_transactions(today):
    """Return (date, source, amount, type, category) rows, oldest first."""
    rng = random.Random(SEED)
    rows = []

    for months_ago in range(MONTHS_OF_HISTORY - 1, -1, -1):
        start = month_start(today, months_ago)
        days_in_month = monthrange(start.year, start.month)[1]
        # The current month is only filled in as far as today.
        latest_day = today.day if months_ago == 0 else days_in_month

        salary = BASE_SALARY
        if months_ago < RAISE_AFTER_MONTHS:
            salary += RAISE_AMOUNT
        rows.append((start, "Monthly Salary", salary, "income", "Salary"))
        rows.append((start, "Apartment Rent", RENT, "expense", "Bills"))

        for day, source, category, amount in FIXED_BILLS:
            if day <= latest_day:
                rows.append((start.replace(day=day), source, amount, "expense", category))

        electricity_day = min(12, latest_day)
        rows.append((
            start.replace(day=electricity_day),
            "Saudi Electricity Company",
            electricity_for(start),
            "expense",
            "Bills",
        ))

        for source, category, low, high, times in REGULAR_SPENDING:
            for _ in range(times):
                rows.append((
                    spending_day(rng, start, latest_day),
                    source,
                    money(rng, low, high),
                    "expense",
                    category,
                ))

        for source, category, low, high in rng.sample(OCCASIONAL, rng.randint(2, 4)):
            rows.append((
                spending_day(rng, start, latest_day),
                source,
                money(rng, low, high),
                "expense",
                category,
            ))

    for months_ago, source, amount, day in EXTRA_INCOME:
        start = month_start(today, months_ago)
        if months_ago > 0 or day <= today.day:
            rows.append((start.replace(day=day), source, amount, "income", "Salary"))

    for months_ago, source, category, amount, day in MAJOR_EXPENSES:
        start = month_start(today, months_ago)
        if months_ago > 0 or day <= today.day:
            rows.append((start.replace(day=day), source, amount, "expense", category))

    rows.sort(key=lambda row: row[0])
    return rows


def build_budgets(rows, today):
    """Budgets sized against what the current month actually spent.

    Derived rather than hardcoded so the demo always shows the same story —
    a couple of categories comfortable, one close to its limit, one over —
    however the seeded amounts happen to fall.
    """
    current_start = month_start(today, 0)
    spent = {}
    for row_date, _, amount, transaction_type, category in rows:
        if transaction_type == "expense" and row_date >= current_start:
            spent[category] = spent.get(category, Decimal(0)) + amount

    # category -> what fraction of this month's spend the limit represents.
    # Below 1.0 means the category is already over budget.
    targets = {
        "Groceries": Decimal("1.35"),
        "Dining": Decimal("0.82"),
        "Transport": Decimal("1.60"),
        "Shopping": Decimal("1.15"),
        "Entertainment": Decimal("1.05"),
    }

    budgets = []
    for category, factor in targets.items():
        limit = (spent.get(category, Decimal("400")) * factor).quantize(Decimal("1"))
        budgets.append((category, max(limit, Decimal("100"))))
    return budgets


def build_import_history(today):
    """Two past imports, so import history has something to show.

    The transactions they created are the real ones seeded above — the batch
    records are attached to that month's rows below, rather than inventing
    extra transactions nobody would recognise.
    """
    records = [
        {"months_ago": 3, "day": 6, "at": "09:14", "total": 34,
         "failed": 0, "duplicates": 0, "status": "completed", "errors": []},
        {"months_ago": 1, "day": 4, "at": "21:38", "total": 21,
         "failed": 2, "duplicates": 3, "status": "partial"},
    ]

    for record in records:
        covered = month_start(today, record["months_ago"])
        # Named after the month it covers, worked out at runtime: a filename
        # with a month in it would otherwise be wrong the moment this script
        # is run in a different one.
        record["filename"] = f"{covered:%Y-%m}-bank-statement.csv"
        record.setdefault("errors", [
            (7, "error.invalid_date_format",
             f"{covered.day:02d}/{covered.month:02d}/{covered.year},Bakery,38.00,expense,Dining"),
            (15, "error.invalid_category",
             f"{covered:%Y-%m}-14,Pet Store,120.00,expense,Pets"),
        ])

    return records


def main():
    today = date.today()
    rows = build_transactions(today)
    budgets = build_budgets(rows, today)
    imports = build_import_history(today)

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("DELETE FROM users WHERE username = %s", (DEMO_USERNAME,))

        password_hash = generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256")
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (DEMO_USERNAME, password_hash, month_start(today, MONTHS_OF_HISTORY - 1)),
        )
        user_id = cursor.fetchone()[0]

        import_ids = {}
        for record in imports:
            day = month_start(today, record["months_ago"]).replace(day=record["day"])
            created = f"{day.isoformat()} {record['at']}"
            cursor.execute(
                """
                INSERT INTO import_batches
                    (user_id, filename, file_hash, created_at, total_rows,
                     successful_rows, failed_rows, duplicate_rows, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    record["filename"],
                    # A stand-in hash: these imports never had a real file.
                    f"{'0' * 56}{record['months_ago']:08d}",
                    created,
                    record["total"],
                    record["total"] - record["failed"] - record["duplicates"],
                    record["failed"],
                    record["duplicates"],
                    record["status"],
                ),
            )
            import_id = cursor.fetchone()[0]
            import_ids[record["months_ago"]] = import_id

            for row_number, error_key, raw_row in record["errors"]:
                cursor.execute(
                    """
                    INSERT INTO import_row_errors (import_id, row_number, error_key, raw_row)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (import_id, row_number, error_key, raw_row),
                )

        # Transactions in a month that was imported carry that import's id, so
        # the summary page shows provenance for rows that really exist.
        imported_months = {
            month_start(today, months_ago): import_id
            for months_ago, import_id in import_ids.items()
        }

        for row_date, source, amount, transaction_type, category in rows:
            import_id = imported_months.get(row_date.replace(day=1))
            cursor.execute(
                """
                INSERT INTO transactions
                    (user_id, date, source, amount, type, category, import_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, row_date, source, amount, transaction_type, category, import_id),
            )

        for category, monthly_limit in budgets:
            cursor.execute(
                "INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s, %s, %s)",
                (user_id, category, monthly_limit),
            )

        connection.commit()

    report(today, rows, budgets)


def report(today, rows, budgets):
    """Print what is on screen, so the presenter knows before the audience."""
    current_start = month_start(today, 0)
    income = sum(a for d, _, a, t, _ in rows if t == "income" and d >= current_start)
    spending = sum(a for d, _, a, t, _ in rows if t == "expense" and d >= current_start)
    first_month = month_start(today, MONTHS_OF_HISTORY - 1)

    print("Demo account ready:")
    print(f"  username     : {DEMO_USERNAME}")
    print(f"  password     : {DEMO_PASSWORD}")
    print()
    print(f"  months       : {first_month:%b %Y} to {today:%b %Y} ({MONTHS_OF_HISTORY})")
    print(f"  transactions : {len(rows)}")
    print("  imports      : 2 (one completed, one partial)")
    print()
    print(f"  {today:%B} income   : {income:,.2f} SAR")
    print(f"  {today:%B} spending : {spending:,.2f} SAR")
    print(f"  {today:%B} net      : {income - spending:,.2f} SAR")
    print()
    print("  budgets:")
    for category, limit in budgets:
        spent = sum(
            a for d, _, a, t, c in rows
            if t == "expense" and c == category and d >= current_start
        )
        state = "OVER" if spent > limit else "ok"
        print(f"    {category:<14} {spent:>9,.2f} / {limit:>8,.2f} SAR  {state}")


if __name__ == "__main__":
    main()
