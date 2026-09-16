from flask import Flask, redirect, render_template, request, flash
from datetime import datetime
from contextlib import contextmanager
import sqlite3

app = Flask(__name__)
app.secret_key = "dev"  # required for flash messages; use env var in production

DB_PATH = "expenses.db"
CATEGORIES = (
    "Groceries",
    "Dining",
    "Transport",
    "Shopping",
    "Bills",
    "Entertainment",
    "Salary",
    "Other",
)

@contextmanager
def get_connection():
    """Yield a sqlite3 connection and guarantee it's closed afterward."""
    connection = sqlite3.connect(DB_PATH)
    try:
        yield connection
    finally:
        connection.close()

def initialize_database():
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                category TEXT NOT NULL DEFAULT 'Other'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                category TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL CHECK (monthly_limit > 0)
            )
        """)
        connection.commit()


def migrate_database():
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]

        if "category" not in columns:
            cursor.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN category TEXT NOT NULL DEFAULT 'Other'
                """
            )
            connection.commit()

initialize_database()
migrate_database()

def validate_transaction_form(form):
    """Validate submitted form data, returning (data, error) tuple."""
    category = form.get("category", "").strip()
    date = form.get("date", "").strip()
    source = form.get("source", "").strip()
    amount_input = form.get("amount", "").strip()
    transaction_type = form.get("type", "").strip().lower()

    if category not in CATEGORIES:
        return None, "Invalid category"

    if not date:
        return None, "Date is required"
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None, "Invalid date format"

    if not source:
        return None, "Source is required"
    if source.isdigit():
        return None, "Source cannot be only numbers"

    try:
        amount = float(amount_input)
    except ValueError:
        return None, "Amount must be a number"
    if amount <= 0:
        return None, "Amount must be greater than 0"

    if transaction_type not in ("income", "expense"):
        return None, "Invalid transaction type"

    return {
        "date": date,
        "source": source,
        "amount": amount,
        "type": transaction_type,
        "category": category,
    }, None


@app.route("/")
def home():
    total_income, total_spending, balance = get_summary()
    spending_by_category = get_spending_by_category()
    monthly_spending = get_monthly_spending()
    budget_status = get_budget_status()

    category_labels = [row[0] for row in spending_by_category]
    category_totals = [row[1] for row in spending_by_category]

    monthly_labels = [row[0] for row in monthly_spending]
    monthly_totals = [row[1] for row in monthly_spending]

    return render_template(
        "index.html",
        total_income=total_income,
        total_spending=total_spending,
        balance=balance,
        spending_by_category=spending_by_category,
        category_labels=category_labels,
        category_totals=category_totals,
        monthly_labels=monthly_labels,
        monthly_totals=monthly_totals,
        budget_status=budget_status
    )


@app.route("/transactions")
def transactions():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    transaction_type = request.args.get("type", "").strip()

    return render_template(
        "transactions.html",
        transactions=get_transactions(search, category, transaction_type),
        search=search,
        category=category,
        transaction_type=transaction_type,
        categories=CATEGORIES
    )


def get_summary():
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                "SELECT SUM(amount) FROM transactions WHERE type = 'income'"
            )
            total_income = cursor.fetchone()[0] or 0

            cursor.execute(
                "SELECT SUM(amount) FROM transactions WHERE type = 'expense'"
            )
            total_spending = cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        total_income = total_spending = 0

    return total_income, total_spending, total_income - total_spending


def get_transactions(search="", category="", transaction_type=""):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            conditions = []
            params = []

            if search:
                conditions.append("source LIKE ?")
                params.append(f"%{search}%")

            if category:
                conditions.append("category = ?")
                params.append(category)

            if transaction_type:
                conditions.append("type = ?")
                params.append(transaction_type)

            query = """
                SELECT id, date, source, amount, type, category
                FROM transactions
            """

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY id"

            cursor.execute(query, params)
            return cursor.fetchall()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        return []


def get_transaction_by_id(transaction_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, date, source, amount, type, category "
                "FROM transactions "
                "WHERE id = ?",
                (transaction_id,)
            )
            return cursor.fetchone()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        return None


@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
def edit_transaction(transaction_id):
    transaction = get_transaction_by_id(transaction_id)
    if transaction is None:
        return "Transaction not found", 404

    if request.method == "POST":
        data, error = validate_transaction_form(request.form)
        if error:
            flash(error)
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
                    SET date = ?, source = ?, amount = ?, type = ?, category = ?
                    WHERE id = ?
                    """,
                    (data["date"], data["source"], data["amount"],
                     data["type"], data["category"], transaction_id)
                )
                connection.commit()
        except sqlite3.Error as e:
            flash(f"Database error: {e}")
            return render_template(
                "edit.html",
                transaction=transaction,
                categories=CATEGORIES
            ), 500

        return redirect("/transactions")

    return render_template("edit.html", transaction=transaction, categories=CATEGORIES)


@app.route("/transactions/add", methods=["GET", "POST"])
def add_transaction():
    if request.method == "POST":
        data, error = validate_transaction_form(request.form)
        if error:
            flash(error)
            return render_template("add.html", categories=CATEGORIES), 400

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO transactions (date, source, amount, type, category)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (data["date"], data["source"], data["amount"], data["type"], data["category"])
                )
                connection.commit()
        except sqlite3.Error as e:
            flash(f"Database error: {e}")
            return render_template("add.html", categories=CATEGORIES), 500

        return redirect("/")

    return render_template("add.html", categories=CATEGORIES)


@app.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
def delete_transaction(transaction_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM transactions WHERE id = ?", (transaction_id,)
            )
            connection.commit()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")

    return redirect("/transactions")


@app.route("/budgets", methods=["GET", "POST"])
def budgets():
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        limit_input = request.form.get("monthly_limit", "").strip()

        if category not in CATEGORIES:
            flash("Invalid category")
            return redirect("/budgets")

        try:
            monthly_limit = float(limit_input)
        except ValueError:
            flash("Monthly limit must be a number")
            return redirect("/budgets")

        if monthly_limit <= 0:
            flash("Monthly limit must be greater than 0")
            return redirect("/budgets")

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO budgets (category, monthly_limit)
                    VALUES (?, ?)
                    ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit
                    """,
                    (category, monthly_limit)
                )
                connection.commit()
        except sqlite3.Error as e:
            flash(f"Database error: {e}")

        return redirect("/budgets")

    return render_template(
        "budgets.html",
        budget_status=get_budget_status(),
        categories=CATEGORIES
    )


@app.route("/budgets/<category>/delete", methods=["POST"])
def delete_budget(category):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM budgets WHERE category = ?", (category,))
            connection.commit()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")

    return redirect("/budgets")


def get_spending_by_category():
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                SELECT category, SUM(amount) AS total
                FROM transactions
                WHERE type = 'expense'
                GROUP BY category
                ORDER BY total DESC
            """)

            return cursor.fetchall()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        return []


def get_monthly_spending():
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
                FROM transactions
                WHERE type = 'expense'
                GROUP BY month
                ORDER BY month
            """)

            return cursor.fetchall()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        return []


def get_budget_status():
    """Return each budget's monthly limit alongside spending for the current month."""
    current_month = datetime.now().strftime("%Y-%m")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                "SELECT category, monthly_limit FROM budgets ORDER BY category"
            )
            budget_limits = cursor.fetchall()

            cursor.execute(
                """
                SELECT category, SUM(amount)
                FROM transactions
                WHERE type = 'expense' AND strftime('%Y-%m', date) = ?
                GROUP BY category
                """,
                (current_month,)
            )
            spending_by_category = dict(cursor.fetchall())
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
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


if __name__ == "__main__":
    app.run(debug=True)