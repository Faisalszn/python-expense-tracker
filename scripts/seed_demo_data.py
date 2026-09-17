"""Create (or reset) a demo account with realistic sample data for showcasing the app.

Usage:
    python scripts/seed_demo_data.py

Safe to re-run any time, including right before a demo: it deletes any
existing account with the same username first (transactions/budgets go
with it via ON DELETE CASCADE), then recreates it from scratch, so the
demo always starts from the same known state.

Uses the same DATABASE_URL / .env as the app itself (via db.py) — run
this with the same environment you run `python app.py` with.
"""

import sys
from datetime import date, timedelta
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

# (days_ago, source, amount, type, category)
# Spans ~3 months so the monthly trend chart has multiple points, with a
# denser cluster in the last two weeks so the current month's budgets and
# category breakdown look populated. Dining is deliberately pushed over its
# budget below to demonstrate the over-budget UI state.
TRANSACTIONS = [
    (95, "Monthly Salary", "8500.00", "income", "Salary"),
    (95, "Rent", "2200.00", "expense", "Bills"),
    (80, "Carrefour", "420.00", "expense", "Groceries"),
    (80, "Uber", "60.00", "expense", "Transport"),
    (78, "Cinema", "130.00", "expense", "Entertainment"),
    (65, "Monthly Salary", "8500.00", "income", "Salary"),
    (63, "Zara", "300.00", "expense", "Shopping"),
    (60, "Restaurant", "150.00", "expense", "Dining"),
    (50, "Electricity Bill", "260.00", "expense", "Bills"),
    (48, "Panda Mart", "380.00", "expense", "Groceries"),
    (45, "Careem", "70.00", "expense", "Transport"),
    (35, "Monthly Salary", "8500.00", "income", "Salary"),
    (33, "Restaurant", "200.00", "expense", "Dining"),
    (30, "Gym Membership", "140.00", "expense", "Entertainment"),
    (12, "Tamimi Markets", "300.00", "expense", "Groceries"),
    (10, "Fancy Dinner", "225.00", "expense", "Dining"),
    (8, "Petrol Station", "90.00", "expense", "Transport"),
    (6, "Amazon", "220.00", "expense", "Shopping"),
    (5, "Freelance Project", "1200.00", "income", "Salary"),
    (3, "Restaurant", "180.50", "expense", "Dining"),
    (2, "Streaming Subscription", "60.00", "expense", "Entertainment"),
    (1, "Grocery Run", "150.00", "expense", "Groceries"),
]

# (category, monthly_limit) — Dining's recent spend (605.50 in the last two
# weeks) comfortably exceeds this, so it renders as over-budget.
BUDGETS = [
    ("Groceries", "900.00"),
    ("Dining", "200.00"),
    ("Transport", "250.00"),
    ("Shopping", "400.00"),
    ("Entertainment", "150.00"),
]


def main():
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("DELETE FROM users WHERE username = %s", (DEMO_USERNAME,))

        password_hash = generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256")
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (DEMO_USERNAME, password_hash),
        )
        user_id = cursor.fetchone()[0]

        today = date.today()
        for days_ago, source, amount, transaction_type, category in TRANSACTIONS:
            cursor.execute(
                """
                INSERT INTO transactions (user_id, date, source, amount, type, category)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, today - timedelta(days=days_ago), source,
                 Decimal(amount), transaction_type, category),
            )

        for category, monthly_limit in BUDGETS:
            cursor.execute(
                """
                INSERT INTO budgets (user_id, category, monthly_limit)
                VALUES (%s, %s, %s)
                """,
                (user_id, category, Decimal(monthly_limit)),
            )

        connection.commit()

    print("Demo account ready:")
    print(f"  username: {DEMO_USERNAME}")
    print(f"  password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
