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


## Version 7 – Analytics Dashboard and Mizan Branding

Version 7 expanded the project from a transaction management tool into a more complete personal finance dashboard with visual analytics and a stronger product identity.

### New Features
- Added spending-by-category analytics
- Added monthly spending trend analysis
- Added a doughnut chart for category-based spending
- Added a line chart for monthly spending
- Added Riyal formatting to financial chart values
- Introduced the Mizan brand identity
- Added a branded navbar and favicon
- Improved the dashboard layout and analytics presentation

### Backend Improvements
- Added SQL aggregation using `SUM()`
- Added grouping with `GROUP BY`
- Added monthly aggregation using SQLite `strftime()`
- Prepared analytics data in Flask before sending it to the frontend
- Converted query results into separate label and value lists for chart rendering

### Frontend Improvements
- Integrated Chart.js for data visualization
- Added a category spending doughnut chart
- Added a monthly spending line chart
- Passed Flask/Jinja data safely into JavaScript using `tojson`
- Added responsive analytics cards
- Added Mizan logo assets and visual branding

### Technologies Introduced
- Chart.js
- JavaScript data visualization
- Jinja `tojson`
- SQL aggregation and grouping
- SQLite date formatting with `strftime()`

### What I Learned
- How to aggregate financial data using SQL
- How `GROUP BY` changes raw database rows into analytical summaries
- How to aggregate data over time using date fields
- How Flask can prepare backend data for frontend visualizations
- How Jinja passes Python data into JavaScript
- How Chart.js uses labels and datasets to render charts
- How to separate JavaScript into static files
- How branding assets are organized and served through Flask's `static` directory
- How backend data, frontend templates, and JavaScript work together in a full-stack application

### Spending by Category Flow

```text
SQLite Transactions
        ↓
WHERE type = 'expense'
        ↓
GROUP BY category
        ↓
SUM(amount)
        ↓
Flask
        ↓
Jinja
        ↓
Chart.js Doughnut Chart
```

## Version 8 – Budgets and Spending Limits

Version 8 introduced budgeting, letting a monthly spending limit be set per category and tracked against real spending.

### New Features
- Set a monthly spending limit per category
- View spending progress against each budget on a dedicated Budgets page
- Show a Budget Status summary on the dashboard
- Highlight categories that go over their monthly limit
- Update a budget by resubmitting a limit for the same category
- Remove a budget

### Backend Improvements
- Added a `budgets` table keyed by category
- Used `INSERT ... ON CONFLICT DO UPDATE` to create or update a budget in one query
- Compared current-month spending (via `strftime('%Y-%m', date)`) against each budget's limit
- Calculated spent, remaining, and percentage-used for each budget

### Frontend Improvements
- Added a Budgets page with a form to set limits and a list of progress bars
- Added a Budget Status section to the dashboard
- Added progress bar styling with a distinct over-budget state
- Added a "Budgets" link to the navbar

### What I Learned
- How to design a table keyed by a natural key instead of an autoincrement id
- How `INSERT ... ON CONFLICT DO UPDATE` (upsert) avoids separate insert/update logic
- How to scope an aggregate SQL query to the current calendar month
- How to turn a ratio into a percentage-based progress bar in the UI

## Version 9 – User Accounts and PostgreSQL

Version 9 turned the app from a single shared ledger into a multi-user application, and replaced SQLite with PostgreSQL as the application database.

### New Features
- Create an account with a username and password
- Log in and log out
- Every transaction and budget is scoped to the logged-in user
- Anonymous visitors are redirected to the login page
- A user can no longer view, edit, or delete another user's transactions or budgets, even by guessing an id in the URL

### Backend Improvements
- Replaced `sqlite3` with `psycopg2` and PostgreSQL
- Added a `users` table storing a username and a hashed password
- Added a `user_id` foreign key to `transactions` and `budgets`, with `ON DELETE CASCADE`
- Changed the `budgets` primary key to `(user_id, category)` so each user has independent budgets
- Hashed passwords with `werkzeug.security.generate_password_hash` / `check_password_hash`
- Added a `login_required` decorator to protect routes
- Rewrote every query to filter by the current session's `user_id`
- Replaced SQLite's `?` placeholders with psycopg2's `%s` placeholders
- Replaced SQLite's `strftime('%Y-%m', date)` with `SUBSTRING(date FROM 1 FOR 7)`
- Read database configuration from a `DATABASE_URL` environment variable via `python-dotenv`

### Frontend Improvements
- Added Login and Create Account pages
- Made the navbar auth-aware: shows Login/Create Account when signed out, and the username plus a Log Out button when signed in

### What I Learned
- How to design multi-tenant tables with a foreign key instead of a single shared table
- Why passwords are hashed instead of stored as plain text, and how `werkzeug.security` does it
- How Flask sessions keep a logged-in user's id between requests
- How a Python decorator can guard multiple routes with one piece of reusable logic
- How SQL dialects differ between SQLite and PostgreSQL (placeholders, date functions, upsert syntax)
- Why every query needs a `WHERE user_id = ...` check, not just the ones a user is "supposed" to hit — otherwise an id in a URL can expose or modify someone else's data
- How to keep secrets like `DATABASE_URL` out of source control with a `.env` file and `.env.example`

### Running Locally

```bash
pip install -r requirements.txt

# create a PostgreSQL database, then set DATABASE_URL
cp .env.example .env
# edit .env with your database credentials

python app.py
```