# Python Expense Tracker

### Version 1 Features

    1. Add a transaction
    2. View all expenses
    3. Sum of expenses only 
    4. Exit the program

## Transaction Data

Each transaction contains:

    - Date
    - Place or source
    - Amount
    - Transaction type: income or expense

## Version 2 Features

    1. Edit Transactions — Select an existing transaction from a numbered list and update its date, source, amount, or type. Leave a field blank to keep its current value.
    2. Delete Transactions — Select an existing transaction from a numbered list and remove it after confirmation.

## Version 3 Update
    1.  Replace JSON persistence with SQLite
        while keeping the same CLI features:
        Add
        View
        Summary
        Edit
        Delete

## Version 4 – Flask Web Application

Version 4 transformed the expense tracker from a command-line application into a browser-based web application using Flask.

### New Features

- Built a Flask web interface for the expense tracker
- Added a dashboard displaying:
  - Total income
  - Total spending
  - Current balance
- Added web forms for creating and editing transactions
- Added a transactions page with:
  - View all transactions
  - Edit transaction
  - Delete transaction
- Added server-side form validation
- Used Jinja template inheritance with a shared `base.html`
- Added responsive CSS for desktop and mobile layouts
- Created a modern Najdi-inspired visual design
- Continued using SQLite as the application database

### Technologies Introduced

- Flask
- Jinja
- HTML
- CSS
- HTTP GET and POST requests

### What I Learned

- How Flask routes connect URLs to Python functions
- How GET and POST requests are used in web applications
- How HTML forms send data to a Flask backend
- How Flask communicates with SQLite
- How Jinja passes Python data into HTML templates
- How template inheritance reduces duplicated HTML
- How to structure a small full-stack web application

### Application Flow

Browser → Flask Routes → Python Logic → SQLite Database
    
## V5 — Transaction Categories

✓ category database column
✓ migration for existing databases
✓ current schema for fresh databases
✓ controlled category list
✓ server-side validation
✓ category on Add
✓ category on Edit
✓ category saved in SQLite
✓ category shown in Transactions

## Version 6 – Search and Filtering

Version 6 introduced dynamic transaction filtering to make it easier to explore stored financial data.

### New Features
- Search transactions by source
- Filter transactions by category
- Filter transactions by transaction type
- Combine multiple filters at the same time
- Clear all active filters
- Preserve selected filters in the interface
- Responsive filter controls for desktop and mobile

### Backend Improvements
- Added GET query parameters using Flask `request.args`
- Updated transaction queries to support dynamic filtering
- Built SQL conditions dynamically based on active filters
- Continued using parameterized SQL queries for safer database access

### What I Learned
- How GET requests and query parameters work in Flask
- The difference between `request.args` and `request.form`
- How to build dynamic SQL queries without duplicating query logic
- How to combine multiple SQL conditions using `AND`
- How parameterized queries help prevent SQL injection
- How frontend filter controls connect to backend query logic

### Example

A filtered request can look like:

```text
/transactions?search=car&category=Groceries&type=expense
