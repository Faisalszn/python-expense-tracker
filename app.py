from functools import wraps
from contextlib import contextmanager
from datetime import datetime
import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
)
from dotenv import load_dotenv
import psycopg2
from psycopg2 import errorcodes
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")  # set SECRET_KEY in production

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/expense_tracker"
)

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
    """Yield a psycopg2 connection and guarantee it's closed afterward."""
    connection = psycopg2.connect(DATABASE_URL)
    try:
        yield connection
    finally:
        connection.close()

def initialize_database():
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                category TEXT NOT NULL DEFAULT 'Other'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                monthly_limit REAL NOT NULL CHECK (monthly_limit > 0),
                PRIMARY KEY (user_id, category)
            )
        """)

        connection.commit()

initialize_database()

def login_required(view):
    """Redirect anonymous visitors to the login page before running a view."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue")
            return redirect("/login")
        return view(*args, **kwargs)

    return wrapped_view

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

def validate_credentials(username, password):
    """Validate a username/password pair, returning an error message or None."""
    if not username:
        return "Username is required"
    if len(password) < 8:
        return "Password must be at least 8 characters"
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        error = validate_credentials(username, password)
        if not error and password != confirm_password:
            error = "Passwords do not match"

        if error:
            flash(error)
            return render_template("register.html"), 400

        password_hash = generate_password_hash(password)

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (username, password_hash)
                )
                user_id = cursor.fetchone()[0]
                connection.commit()
        except psycopg2.IntegrityError as e:
            if e.pgcode == errorcodes.UNIQUE_VIOLATION:
                flash("Username is already taken")
            else:
                flash(f"Database error: {e}")
            return render_template("register.html"), 400
        except psycopg2.Error as e:
            flash(f"Database error: {e}")
            return render_template("register.html"), 500

        session["user_id"] = user_id
        session["username"] = username
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT id, password_hash FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
        except psycopg2.Error as e:
            flash(f"Database error: {e}")
            return render_template("login.html"), 500

        if user is None or not check_password_hash(user[1], password):
            flash("Invalid username or password")
            return render_template("login.html"), 400

        session["user_id"] = user[0]
        session["username"] = username
        return redirect("/")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def home():
    user_id = session["user_id"]

    total_income, total_spending, balance = get_summary(user_id)
    spending_by_category = get_spending_by_category(user_id)
    monthly_spending = get_monthly_spending(user_id)
    budget_status = get_budget_status(user_id)

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
@login_required
def transactions():
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
        flash(f"Database error: {e}")
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
        flash(f"Database error: {e}")
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
        flash(f"Database error: {e}")
        return None


@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    transaction = get_transaction_by_id(transaction_id, session["user_id"])
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
                    SET date = %s, source = %s, amount = %s, type = %s, category = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (data["date"], data["source"], data["amount"], data["type"],
                     data["category"], transaction_id, session["user_id"])
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(f"Database error: {e}")
            return render_template(
                "edit.html",
                transaction=transaction,
                categories=CATEGORIES
            ), 500

        return redirect("/transactions")

    return render_template("edit.html", transaction=transaction, categories=CATEGORIES)


@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
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
                    INSERT INTO transactions (user_id, date, source, amount, type, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (session["user_id"], data["date"], data["source"],
                     data["amount"], data["type"], data["category"])
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(f"Database error: {e}")
            return render_template("add.html", categories=CATEGORIES), 500

        return redirect("/")

    return render_template("add.html", categories=CATEGORIES)


@app.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM transactions WHERE id = %s AND user_id = %s",
                (transaction_id, session["user_id"])
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(f"Database error: {e}")

    return redirect("/transactions")


@app.route("/budgets", methods=["GET", "POST"])
@login_required
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
                    INSERT INTO budgets (user_id, category, monthly_limit)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, category)
                    DO UPDATE SET monthly_limit = excluded.monthly_limit
                    """,
                    (session["user_id"], category, monthly_limit)
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(f"Database error: {e}")

        return redirect("/budgets")

    return render_template(
        "budgets.html",
        budget_status=get_budget_status(session["user_id"]),
        categories=CATEGORIES
    )


@app.route("/budgets/<category>/delete", methods=["POST"])
@login_required
def delete_budget(category):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM budgets WHERE category = %s AND user_id = %s",
                (category, session["user_id"])
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(f"Database error: {e}")

    return redirect("/budgets")


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
        flash(f"Database error: {e}")
        return []


def get_monthly_spending(user_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT SUBSTRING(date FROM 1 FOR 7) AS month, SUM(amount) AS total
                FROM transactions
                WHERE type = 'expense' AND user_id = %s
                GROUP BY month
                ORDER BY month
                """,
                (user_id,)
            )

            return cursor.fetchall()
    except psycopg2.Error as e:
        flash(f"Database error: {e}")
        return []


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
                    AND SUBSTRING(date FROM 1 FOR 7) = %s
                GROUP BY category
                """,
                (user_id, current_month)
            )
            spending_by_category = dict(cursor.fetchall())
    except psycopg2.Error as e:
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
