import sqlite3
from datetime import datetime


def initialize_database():
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        source TEXT NOT NULL,
        amount REAL NOT NULL CHECK (amount > 0),
        type TEXT NOT NULL CHECK (type IN ('income', 'expense'))
    )
    """)
    connection.commit()
    connection.close()


def show_summary():
    """Print total income, spending, and balance."""
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute("SELECT type, SUM(amount) FROM transactions GROUP BY type")
    totals = dict(cursor.fetchall())
    connection.close()

    total_income = totals.get("income", 0.0)
    total_spending = totals.get("expense", 0.0)
    balance = total_income - total_spending
    print(f"Total income: {total_income:.2f}")
    print(f"Total spending: {total_spending:.2f}")
    print(f"Balance: {balance:.2f}")


def get_transactions():
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT id, date, source, amount, type FROM transactions ORDER BY id"
    )
    rows = cursor.fetchall()
    connection.close()

    return rows


def get_transaction_by_id(transaction_id):
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT id, date, source, amount, type FROM transactions WHERE id = ?",
        (transaction_id,)
    )
    row = cursor.fetchone()
    connection.close()

    return row


def view_transactions():
    """Print all transactions, one per block."""
    transactions = get_transactions()
    if not transactions:
        print("No transactions found.")
        return

    for transaction_id, date, source, amount, transaction_type in transactions:
        print(f"ID: {transaction_id}")
        print(f"Date: {date}")
        print(f"Source: {source}")
        print(f"Amount: {amount}")
        print(f"Type: {transaction_type}")
        print("--------------------")


def prompt_date():
    while True:
        date = input("Enter the date (YYYY-MM-DD): ")
        try:
            datetime.strptime(date, "%Y-%m-%d")
            return date
        except ValueError:
            print("Invalid date format. Please enter in YYYY-MM-DD format.")


def prompt_source():
    while True:
        source = input("Enter the source of the transaction: ").strip()
        if not source:
            print("Source cannot be empty.")
        elif source.isdigit():
            print("Source cannot be only numbers. Please enter a valid source.")
        else:
            return source


def prompt_amount():
    while True:
        try:
            amount = float(input("Enter the amount of the transaction: "))
            if amount <= 0:
                print("Amount must be greater than 0.")
                continue
            return amount
        except ValueError:
            print("Invalid amount. Please enter a number.")


def prompt_type():
    while True:
        transaction_type = input(
            "Enter the type of the transaction (income/expense): "
        ).strip().lower()
        if transaction_type in ("income", "expense"):
            return transaction_type
        print("Invalid transaction type. Please enter 'income' or 'expense'.")


def insert_transaction(transaction):
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO transactions (date, source, amount, type) VALUES (?, ?, ?, ?)",
        (transaction["Date"], transaction["Source"], transaction["Amount"], transaction["Type"])
    )
    connection.commit()
    connection.close()


def add_transaction():
    transaction = {
        "Date": prompt_date(),
        "Source": prompt_source(),
        "Amount": prompt_amount(),
        "Type": prompt_type(),
    }
    insert_transaction(transaction)
    print("Transaction added successfully.")


def select_transaction():
    """Display transactions and let the user pick one by database id."""
    transactions = get_transactions()
    if not transactions:
        print("No transactions found.")
        return None

    for transaction_id, date, source, amount, transaction_type in transactions:
        print(f"{transaction_id}. {date} | {source} | {amount} | {transaction_type}")

    while True:
        choice = input("Enter the id of the transaction (or 0 to cancel): ")
        if choice == "0":
            return None
        try:
            transaction_id = int(choice)
            if any(row[0] == transaction_id for row in transactions):
                return transaction_id
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def update_transaction(transaction_id, date, source, amount, transaction_type):
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE transactions SET date = ?, source = ?, amount = ?, type = ? WHERE id = ?",
        (date, source, amount, transaction_type, transaction_id)
    )
    connection.commit()
    connection.close()


def edit_transaction():
    """Let the user edit an existing transaction's fields."""
    transaction_id = select_transaction()
    if transaction_id is None:
        return

    row = get_transaction_by_id(transaction_id)
    if row is None:
        print("Transaction no longer exists.")
        return

    _, date, source, amount, transaction_type = row
    print("Leave a field blank to keep its current value.")

    new_date = input(f"Date [{date}]: ").strip()
    if new_date:
        try:
            datetime.strptime(new_date, "%Y-%m-%d")
            date = new_date
        except ValueError:
            print("Invalid date format, keeping previous value.")

    new_source = input(f"Source [{source}]: ").strip()
    if new_source:
        if new_source.isdigit():
            print("Source cannot be only numbers, keeping previous value.")
        else:
            source = new_source

    new_amount = input(f"Amount [{amount}]: ").strip()
    if new_amount:
        try:
            value = float(new_amount)
            if value > 0:
                amount = value
            else:
                print("Amount must be greater than 0, keeping previous value.")
        except ValueError:
            print("Invalid amount, keeping previous value.")

    new_type = input(f"Type [{transaction_type}]: ").strip().lower()
    if new_type:
        if new_type in ("income", "expense"):
            transaction_type = new_type
        else:
            print("Invalid type, keeping previous value.")

    update_transaction(transaction_id, date, source, amount, transaction_type)
    print("Transaction updated successfully.")


def delete_transaction_by_id(transaction_id):
    connection = sqlite3.connect("expenses.db")
    cursor = connection.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    connection.commit()
    connection.close()


def delete_transaction():
    """Let the user pick and delete an existing transaction."""
    transaction_id = select_transaction()
    if transaction_id is None:
        return

    confirm = input("Are you sure you want to delete this transaction? (y/n): ").strip().lower()
    if confirm == "y":
        delete_transaction_by_id(transaction_id)
        print("Transaction deleted successfully.")
    else:
        print("Delete cancelled.")


def main():
    initialize_database()

    menu_actions = {
        "1": add_transaction,
        "2": view_transactions,
        "3": show_summary,
        "4": edit_transaction,
        "5": delete_transaction,
    }

    while True:
        print("\nExpense Tracker\n")
        print("1. Add transaction")
        print("2. View all transactions")
        print("3. Show summary")
        print("4. Edit a transaction")
        print("5. Delete a transaction")
        print("6. Exit")

        choice = input("Please choose an option: ")

        if choice == "6":
            break

        action = menu_actions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()