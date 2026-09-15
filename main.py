import json
from datetime import datetime

TRANSACTIONS_FILE = "transactions.json"


def show_summary(transactions):
    """Print total income, spending, and balance."""
    total_income = sum(t['Amount'] for t in transactions if t['Type'] == 'income')
    total_spending = sum(t['Amount'] for t in transactions if t['Type'] == 'expense')
    balance = total_income - total_spending
    print(f"Total income: {total_income:.2f}")
    print(f"Total spending: {total_spending:.2f}")
    print(f"Balance: {balance:.2f}")


def save_transactions(transactions):
    """Persist transactions to disk as JSON."""
    try:
        with open(TRANSACTIONS_FILE, "w") as file:
            json.dump(transactions, file, indent=4)
    except OSError as e:
        print(f"Error saving transactions: {e}")


def view_transactions(transactions):
    """Print all transactions, one per block."""
    if not transactions:
        print("No transactions found.")
        return

    for transaction in transactions:
        print(f"Date: {transaction['Date']}")
        print(f"Source: {transaction['Source']}")
        print(f"Amount: {transaction['Amount']}")
        print(f"Type: {transaction['Type']}")
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


def add_transaction(transactions):
    """Prompt the user for transaction details and append it to the list."""
    transaction = {
        "Date": prompt_date(),
        "Source": prompt_source(),
        "Amount": prompt_amount(),
        "Type": prompt_type(),
    }

    transactions.append(transaction)
    save_transactions(transactions)
    print("Transaction added successfully.")


def select_transaction(transactions):
    """Display numbered transactions and let the user pick one by index."""
    if not transactions:
        print("No transactions found.")
        return None

    for i, transaction in enumerate(transactions, start=1):
        print(f"{i}. {transaction['Date']} | {transaction['Source']} | "
              f"{transaction['Amount']} | {transaction['Type']}")

    while True:
        choice = input("Enter the number of the transaction (or 0 to cancel): ")
        if choice == "0":
            return None
        try:
            index = int(choice) - 1
            if 0 <= index < len(transactions):
                return index
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def edit_transaction(transactions):
    """Let the user edit an existing transaction's fields."""
    index = select_transaction(transactions)
    if index is None:
        return

    transaction = transactions[index]
    print("Leave a field blank to keep its current value.")

    date = input(f"Date [{transaction['Date']}]: ").strip()
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
            transaction["Date"] = date
        except ValueError:
            print("Invalid date format, keeping previous value.")

    source = input(f"Source [{transaction['Source']}]: ").strip()
    if source:
        if source.isdigit():
            print("Source cannot be only numbers, keeping previous value.")
        else:
            transaction["Source"] = source

    amount = input(f"Amount [{transaction['Amount']}]: ").strip()
    if amount:
        try:
            value = float(amount)
            if value > 0:
                transaction["Amount"] = value
            else:
                print("Amount must be greater than 0, keeping previous value.")
        except ValueError:
            print("Invalid amount, keeping previous value.")

    transaction_type = input(f"Type [{transaction['Type']}]: ").strip().lower()
    if transaction_type:
        if transaction_type in ("income", "expense"):
            transaction["Type"] = transaction_type
        else:
            print("Invalid type, keeping previous value.")

    save_transactions(transactions)
    print("Transaction updated successfully.")


def delete_transaction(transactions):
    """Let the user pick and delete an existing transaction."""
    index = select_transaction(transactions)
    if index is None:
        return

    confirm = input("Are you sure you want to delete this transaction? (y/n): ").strip().lower()
    if confirm == "y":
        transactions.pop(index)
        save_transactions(transactions)
        print("Transaction deleted successfully.")
    else:
        print("Delete cancelled.")


def load_transactions():
    """Load transactions from disk, returning an empty list on failure."""
    try:
        with open(TRANSACTIONS_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def main():
    transactions = load_transactions()

    menu_actions = {
        "1": lambda: add_transaction(transactions),
        "2": lambda: view_transactions(transactions),
        "3": lambda: show_summary(transactions),
        "4": lambda: edit_transaction(transactions),
        "5": lambda: delete_transaction(transactions),
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