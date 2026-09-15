import json
from datetime import datetime
def show_summary(transactions):
    total_income = sum(transaction['Amount'] for transaction in transactions if transaction['Type'] == 'income')
    total_spending = sum(transaction['Amount'] for transaction in transactions if transaction['Type'] == 'expense')
    balance = total_income - total_spending
    print(f"Total income: {total_income:.2f}")
    print(f"Total spending: {total_spending:.2f}")
    print(f"Balance: {balance:.2f}")
def save_transactions(transactions):
    with open("transactions.json", "w") as file:
        json.dump(transactions, file, indent=4)
def view_transactions(transactions):
    if not transactions:
        print("No transactions found.")
    else:
        for transaction in transactions:
            print(f"Date: {transaction['Date']}\nSource: {transaction['Source']}\nAmount: {transaction['Amount']}\nType: {transaction['Type']}\n")
            print("--------------------")
def add_transaction(transactions):
    while True:
        date = input("Enter the date (YYYY-MM-DD): ")

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Please enter in YYYY-MM-DD format.")
            continue

        break

    while True:
        source = input("Enter the source of the transaction: ").strip()

        if not source:
            print("Source cannot be empty.")
            continue

        break

    while True:
        try:
            amount = float(input("Enter the amount of the transaction: "))

            if amount <= 0:
                print("Amount must be greater than 0.")
                continue

            break

        except ValueError:
            print("Invalid amount. Please enter a number.")

    while True:
        transaction_type = input(
            "Enter the type of the transaction (income/expense): "
        ).strip().lower()

        if transaction_type not in ["income", "expense"]:
            print("Invalid transaction type. Please enter 'income' or 'expense'.")
            continue

        break

    transaction = {
        "Date": date,
        "Source": source,
        "Amount": amount,
        "Type": transaction_type
    }

    transactions.append(transaction)
    save_transactions(transactions)
    print("Transaction added successfully.")

def load_transactions():
    try:
        with open("transactions.json", "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
transactions = load_transactions()

while True:
    print("Expense Tracker\n")

    print("1. Add transaction")
    print("2. View all transactions")
    print("3. Show total spending")
    print("4. Exit")

    choice = input("Please choose an option: ")
    if choice == "1":
        add_transaction(transactions)
        continue
    elif choice == "2":
        view_transactions(transactions)
        continue
    elif choice == "3":
        show_summary(transactions)
        continue
    elif choice == "4":
        break
    else:
        print("Invalid choice. Please try again.")