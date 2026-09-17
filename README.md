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
```

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

## Version 9.5 – Profile, Security Hardening, and Localization

Version 9.5 rounded out the account system from V9 with a real profile page, several industry-standard security defenses, and English/Arabic localization, plus a themed date picker and stricter transaction validation.

### New Features
- A Profile page showing the username and "member since" date
- Change password from the Profile page (requires the current password)
- Delete account from the Profile page (requires a password confirmation; cascades to all of that user's transactions and budgets)
- Account lockout after 5 failed login attempts, with a 15-minute cooldown
- A language switcher (English / Arabic) in the navbar and on the Profile page, saved per-account and applied immediately, including a right-to-left layout for Arabic
- A themed date picker (flatpickr) on Add/Edit Transaction that matches the site's color palette instead of the browser's native calendar
- Confirmed empty/missing/whitespace-only dates are rejected server-side and never stored (this was already enforced by V9's validation — verified end-to-end rather than re-implemented)

### Backend Improvements
- Added CSRF protection (Flask-WTF) to every form in the app
- Hardened session cookies: `HttpOnly`, `SameSite=Lax`, and `Secure` when `FLASK_ENV=production`
- Debug mode is now controlled by a `FLASK_DEBUG` environment variable instead of being hardcoded
- Added `language`, `created_at`, `failed_login_attempts`, and `locked_until` columns to `users` via an `ADD COLUMN IF NOT EXISTS` migration
- Added a small `translations.py` module (English/Arabic string tables) and a `t()` Jinja helper injected via a Flask context processor, shared between templates and backend flash messages
- Login now checks and updates the lockout state in the same request instead of only checking the password

### Frontend Improvements
- New Profile page with account info, a change-password form, a language selector, and a "danger zone" delete-account form
- Extracted a shared `_budget_card.html` partial so the dashboard and Budgets page render identical budget cards from one template instead of two copies
- Every page's static text and every flash/validation message now runs through the translation layer
- `dir="rtl"` is applied automatically when Arabic is selected, with matching CSS overrides for layout, borders, and spacing
- flatpickr is themed with the site's existing CSS custom properties (same brown/terracotta/sand palette) instead of introducing a new color scheme

### What I chose not to build in this version
Phone/SMS and email-based sign-in or password reset both need a paid third-party account (Twilio, SendGrid/SMTP) to actually deliver anything, and passkeys (WebAuthn) are a large, separable feature. All three were deferred rather than half-implemented — see "What I Learned" below for the reasoning.

### What I Learned
- Why CSRF protection matters for any form-based app, and how Flask-WTF wires a token into the session and validates it on every unsafe request
- The difference between authentication (who you are) and account lockout (slowing down someone guessing who you are)
- Why password confirmation is required before sensitive actions like changing a password or deleting an account, even though the user is already logged in
- How to build a minimal i18n layer without a heavy framework: one lookup dictionary per language, one helper function, and a context processor
- Why `dir="rtl"` alone isn't enough for a real right-to-left experience — spacing, borders, and flex/flow direction all need explicit overrides
- That "looks stylable" and "is stylable" are different for native form controls — the native date picker can't be recolored, which is why a themed replacement (flatpickr) exists
- That deferring a feature (phone/email/passkey login) is sometimes the more honest engineering choice than shipping a fake or broken version of it

### Patch: Data Integrity and Localization Fixes

A code review of V9.5 caught several issues worth fixing before treating it as done, in roughly this priority order:

- **Money was stored as `REAL`.** Floating-point columns can silently misrepresent currency values. Changed `transactions.amount` and `budgets.monthly_limit` to `NUMERIC(12, 2)`, switched all amount parsing from `float()` to `Decimal()` (rejecting non-finite values like `NaN`/`Infinity`, which `Decimal` — unlike `float` — accepts as valid input by default), and converted to `float` only at the one place that actually needs it: building JSON for Chart.js.
- **Dates were stored as `TEXT`.** Changed `transactions.date` to a native `DATE` column and replaced the `SUBSTRING(date FROM 1 FOR 7)` month-grouping hack with `TO_CHAR(date, 'YYYY-MM')`.
- **Migrating existing data safely.** Both changes ship as a migration (`ALTER COLUMN ... TYPE ... USING ...`) guarded by a check against `information_schema.columns`, so it upgrades an existing V9/V9.5 database once and doesn't rewrite the table on every subsequent app startup.
- **Old data files were still committed.** Removed the tracked `expenses.db` and `transactions.json` (both are runtime artifacts of the CLI tool/early versions, not source) and fixed a `.gitignore` typo (`expense.db` → `expenses.db`) that had left the real file untracked-but-not-ignored.
- **Arabic localization was incomplete.** Category names (`Groceries`, `Dining`, etc.), the "member since" month name on the Profile page, and flatpickr's calendar were all still English-only regardless of the selected language. Added `category.*` and `month.*` translation keys, and flatpickr now loads its Arabic locale file when Arabic is selected.
- **`SECRET_KEY` had a silent insecure fallback.** The app now refuses to start if `FLASK_ENV=production` and `SECRET_KEY` is still unset (or left as the `"dev"` default), instead of quietly running with a guessable session-signing key.
- **A broken Markdown fence in this README.** The Version 6 section opened a ` ```text ` block that was never closed, which caused GitHub to render the entire Version 7 section as literal preformatted text.

### What I Learned (Patch)
- Why `NUMERIC`/`Decimal` — not `REAL`/`float` — is the correct choice for money, and why `Decimal` needs its own non-finite check (`NaN`/`Infinity` are valid `Decimal` values, and PostgreSQL's `NUMERIC` type sorts `NaN` as greater than any other value, so a naive `> 0` check does not reject it)
- Where it's correct to convert exact values to `float`: only at a system boundary that genuinely can't consume anything else (Chart.js/JSON), never in the storage or business-logic layer
- How to make a schema migration idempotent for a value that already matches, instead of unconditionally re-running an expensive `ALTER COLUMN TYPE` full-table rewrite on every deploy
- That translating UI chrome is necessary but not sufficient for real localization — the data flowing through that chrome (category names, dates, third-party widgets) needs the same treatment
- That a convenient default (`SECRET_KEY = "dev"`) is a legitimate developer-experience choice for local development and a legitimate vulnerability if it silently ships to production