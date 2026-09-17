from functools import wraps
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from math import ceil
import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
)
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
import psycopg2
from psycopg2 import errorcodes
from werkzeug.security import check_password_hash, generate_password_hash

from translations import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, translate

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")  # set SECRET_KEY in production

if os.environ.get("FLASK_ENV") == "production" and app.secret_key == "dev":
    raise RuntimeError(
        "SECRET_KEY must be set via environment variable when FLASK_ENV=production"
    )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Only require HTTPS-only cookies once the app is actually served over HTTPS.
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

csrf = CSRFProtect(app)

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

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_LOCKOUT_MINUTES = 15

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
                date DATE NOT NULL,
                source TEXT NOT NULL,
                amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                category TEXT NOT NULL DEFAULT 'Other'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                monthly_limit NUMERIC(12, 2) NOT NULL CHECK (monthly_limit > 0),
                PRIMARY KEY (user_id, category)
            )
        """)

        connection.commit()

def _migrate_column_type(cursor, table, column, expected_data_type, alter_clause):
    """Change a column's type only if it doesn't already match, so repeated
    app startups don't rewrite the whole table every time."""
    cursor.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column)
    )
    row = cursor.fetchone()
    if row and row[0] != expected_data_type:
        cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {alter_clause}")

def migrate_database():
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'en'"
        )
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at "
            "TIMESTAMP NOT NULL DEFAULT now()"
        )
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts "
            "INTEGER NOT NULL DEFAULT 0"
        )
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP"
        )

        # Older databases created before money/dates had proper types.
        _migrate_column_type(
            cursor, "transactions", "amount", "numeric",
            "NUMERIC(12, 2) USING amount::numeric(12, 2)"
        )
        _migrate_column_type(
            cursor, "budgets", "monthly_limit", "numeric",
            "NUMERIC(12, 2) USING monthly_limit::numeric(12, 2)"
        )
        _migrate_column_type(
            cursor, "transactions", "date", "date",
            "DATE USING date::date"
        )

        connection.commit()

initialize_database()
migrate_database()

def t(key, **kwargs):
    """Translate `key` into the current session's language."""
    return translate(key, session.get("language", DEFAULT_LANGUAGE), **kwargs)

@app.context_processor
def inject_i18n():
    lang = session.get("language", DEFAULT_LANGUAGE)
    return {
        "t": t,
        "lang": lang,
        "text_dir": "rtl" if lang == "ar" else "ltr",
    }

def login_required(view):
    """Redirect anonymous visitors to the login page before running a view."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash(t("error.login_required"))
            return redirect("/login")
        return view(*args, **kwargs)

    return wrapped_view

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

def validate_credentials(username, password):
    """Validate a username/password pair, returning an error key or None."""
    if not username:
        return "error.username_required"
    if len(password) < 8:
        return "error.password_too_short"
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        error = validate_credentials(username, password)
        if not error and password != confirm_password:
            error = "error.passwords_mismatch"

        if error:
            flash(t(error))
            return render_template("register.html"), 400

        # pbkdf2 avoids relying on hashlib.scrypt, which isn't available on
        # Python builds linked against LibreSSL instead of OpenSSL (e.g. macOS's
        # system Python).
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, language)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (username, password_hash, session.get("language", DEFAULT_LANGUAGE))
                )
                user_id = cursor.fetchone()[0]
                connection.commit()
        except psycopg2.IntegrityError as e:
            if e.pgcode == errorcodes.UNIQUE_VIOLATION:
                flash(t("error.username_taken"))
            else:
                flash(t("error.database", error=e))
            return render_template("register.html"), 400
        except psycopg2.Error as e:
            flash(t("error.database", error=e))
            return render_template("register.html"), 500

        session["user_id"] = user_id
        session["username"] = username
        return redirect("/")

    return render_template("register.html")


def get_user_by_username(username):
    """Return (id, password_hash, language, failed_login_attempts, locked_until)."""
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, password_hash, language, failed_login_attempts, locked_until
                FROM users
                WHERE username = %s
                """,
                (username,)
            )
            return cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return None


def record_failed_login(user_id, failed_attempts):
    """Increment the failed-attempt counter, locking the account past the limit."""
    new_attempts = failed_attempts + 1
    locked_until = None
    if new_attempts >= LOGIN_ATTEMPT_LIMIT:
        locked_until = datetime.now() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
        new_attempts = 0

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET failed_login_attempts = %s, locked_until = %s WHERE id = %s",
                (new_attempts, locked_until, user_id)
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))


def record_successful_login(user_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
                (user_id,)
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if user is not None:
            user_id, password_hash, language, failed_attempts, locked_until = user

            if locked_until is not None and locked_until > datetime.now():
                minutes_left = ceil((locked_until - datetime.now()).total_seconds() / 60)
                flash(t("error.account_locked", minutes=minutes_left))
                return render_template("login.html"), 429

            if check_password_hash(password_hash, password):
                record_successful_login(user_id)
                session["user_id"] = user_id
                session["username"] = username
                session["language"] = language or DEFAULT_LANGUAGE
                return redirect("/")

            record_failed_login(user_id, failed_attempts)

        flash(t("error.invalid_login"))
        return render_template("login.html"), 400

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")


@app.route("/language/<lang>", methods=["POST"])
def set_language(lang):
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    session["language"] = lang

    if "user_id" in session:
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "UPDATE users SET language = %s WHERE id = %s",
                    (lang, session["user_id"])
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(t("error.database", error=e))

    return redirect(request.referrer or "/")


@app.route("/profile")
@login_required
def profile():
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT username, created_at, language FROM users WHERE id = %s",
                (session["user_id"],)
            )
            user = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        user = None

    return render_template(
        "profile.html",
        username=user[0] if user else session.get("username"),
        member_since=user[1] if user else None,
        languages=SUPPORTED_LANGUAGES
    )


@app.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new_password = request.form.get("confirm_new_password", "")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (session["user_id"],)
            )
            row = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    if row is None or not check_password_hash(row[0], current_password):
        flash(t("error.current_password_incorrect"))
        return redirect("/profile")

    error = validate_credentials(session.get("username", ""), new_password)
    if not error and new_password != confirm_new_password:
        error = "error.passwords_mismatch"
    if not error and check_password_hash(row[0], new_password):
        error = "error.new_password_same"

    if error:
        flash(t(error))
        return redirect("/profile")

    new_password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_password_hash, session["user_id"])
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    flash(t("success.password_changed"))
    return redirect("/profile")


@app.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (session["user_id"],)
            )
            row = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    if row is None or not check_password_hash(row[0], password):
        flash(t("error.delete_password_incorrect"))
        return redirect("/profile")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (session["user_id"],))
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    session.clear()
    flash(t("success.account_deleted"))
    return redirect("/login")


@app.route("/")
@login_required
def home():
    user_id = session["user_id"]

    total_income, total_spending, balance = get_summary(user_id)
    spending_by_category = get_spending_by_category(user_id)
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


@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
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


@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
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
        flash(t("error.database", error=e))

    return redirect("/transactions")


@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
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
        flash(t("error.database", error=e))

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


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
