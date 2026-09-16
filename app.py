from flask import Flask, redirect, render_template, request, flash
from datetime import datetime
from contextlib import contextmanager
import sqlite3

app = Flask(__name__)
app.secret_key = "dev"  # required for flash messages; use env var in production

DB_PATH = "expenses.db"


@contextmanager
def get_connection():
    """Yield a sqlite3 connection and guarantee it's closed afterward."""
    connection = sqlite3.connect(DB_PATH)
    try:
        yield connection
    finally:
        connection.close()


def validate_transaction_form(form):
    """Validate submitted form data, returning (data, error) tuple."""
    date = form.get("date", "").strip()
    source = form.get("source", "").strip()
    amount_input = form.get("amount", "").strip()
    transaction_type = form.get("type", "").strip().lower()

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
    }, None


@app.route("/")
def home():
    total_income, total_spending, balance = get_summary()

    return render_template(
        "index.html",
        total_income=total_income,
        total_spending=total_spending,
        balance=balance
    )


@app.route("/transactions")
def transactions():
    return render_template(
        "transactions.html",
        transactions=get_transactions()
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


def get_transactions():
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT id, date, source, amount, type
                FROM transactions
                ORDER BY id
            """)
            return cursor.fetchall()
    except sqlite3.Error as e:
        flash(f"Database error: {e}")
        return []


def get_transaction_by_id(transaction_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, date, source, amount, type FROM transactions WHERE id = ?",
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
            return render_template("edit.html", transaction=transaction), 400

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE transactions
                    SET date = ?, source = ?, amount = ?, type = ?
                    WHERE id = ?
                    """,
                    (data["date"], data["source"], data["amount"],
                     data["type"], transaction_id)
                )
                connection.commit()
        except sqlite3.Error as e:
            flash(f"Database error: {e}")
            return render_template("edit.html", transaction=transaction), 500

        return redirect("/transactions")

    return render_template("edit.html", transaction=transaction)


@app.route("/transactions/add", methods=["GET", "POST"])
def add_transaction():
    if request.method == "POST":
        data, error = validate_transaction_form(request.form)
        if error:
            flash(error)
            return render_template("add.html"), 400

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO transactions (date, source, amount, type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (data["date"], data["source"], data["amount"], data["type"])
                )
                connection.commit()
        except sqlite3.Error as e:
            flash(f"Database error: {e}")
            return render_template("add.html"), 500

        return redirect("/")

    return render_template("add.html")


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


if __name__ == "__main__":
    app.run(debug=True)