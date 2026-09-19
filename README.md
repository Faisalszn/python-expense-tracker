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

python migrate.py   # applies any pending database migrations
python app.py       # starts the Flask development server
```

### Running in Production

`python app.py` runs Flask's development server, which isn't meant to serve real traffic. In production, Gunicorn runs the app instead, and migrations are applied as their own step beforehand rather than automatically on startup — otherwise every Gunicorn worker process would race to apply them when it boots.

```bash
python migrate.py
gunicorn app:app --bind 0.0.0.0:$PORT
```

### Running Tests

```bash
pip install -r requirements-dev.txt

# create a SEPARATE database for tests (running them truncates its tables)
export TEST_DATABASE_URL=postgresql://username:password@localhost:5432/expense_tracker_test

ruff check .
pytest tests/ -v
```

CI (`.github/workflows/ci.yml`) runs both of these on every push and pull request, against a PostgreSQL service container.

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

## Version 10 – Production Readiness and Architecture

By V9.5 `app.py` had grown to roughly 26 KB and held authentication, database setup/migrations, profile logic, transactions, budgets, analytics, and localization wiring in one module, with no automated tests and no CI. Version 10 is not a user-facing feature: it's the refactor that makes the codebase safe to keep extending, with the priorities set by a code review of the V9.5 branch (tests, real migrations, and CI mattering more at this point than another feature).

### New Features (for contributors, not end users)
- A real migration system: numbered `.sql` files in `migrations/`, tracked in a `schema_migrations` table, applied at most once per database
- A pytest suite (55 tests) running against a real PostgreSQL database, covering auth, transactions, budgets, profile actions, and security (CSRF, lockout, cross-user access)
- GitHub Actions CI: lint (`ruff`) and the full test suite against a Postgres service container, on every push and pull request

### Backend Improvements
- Split the monolithic `app.py` into Blueprints by feature area: `blueprints/auth.py`, `blueprints/profile.py`, `blueprints/dashboard.py`, `blueprints/transactions.py`, `blueprints/budgets.py`, with shared `constants.py` (categories) and `i18n.py` (the `t()` helper) modules
- `app.py` is now a ~45-line application factory (`create_app()`) that wires config, CSRF, i18n, blueprints, and (at real startup, not in the factory) migrations together
- Replaced the hand-rolled `initialize_database()`/`migrate_database()` functions with `db.py`'s `run_migrations()`, which applies any `migrations/*.sql` file not yet recorded in `schema_migrations` — each migration now runs exactly once per database instead of re-checking column types on every app startup
- Fixed a real regression the refactor introduced and caught with a manual end-to-end pass, not just the test suite: `.env` values were silently not loading, because `db.py`'s module-level `DATABASE_URL` was evaluated (via the blueprint imports) before `app.py` ever called `load_dotenv()`. Fixed by having `db.py` load its own `.env` immediately before reading the variable it needs, instead of relying on import order elsewhere in the app
- Removed the tracked `expenses.db`/`transactions.json` follow-through: they were already deleted in the previous patch, but `.gitignore` now also excludes `.pytest_cache/` and `.ruff_cache/`

### What I Learned
- Why "it works" and "it's tested" are different claims — the pytest suite caught nothing new in application logic (everything had already been manually verified), but running the *whole* suite against the *refactored* code is what caught the `.env` loading regression, which manual spot-checks of individual routes had missed
- Why a real migration tracking table (`schema_migrations`) is simpler than the guard-and-recheck approach from the previous patch, not just "more proper" — once a migration is recorded as applied, it never needs to inspect `information_schema` again
- How Python's module-level code executes exactly once, at first import, regardless of which import statement triggers it — and why that makes "where do I call `load_dotenv()`" an actual design decision, not a stylistic one
- How Flask Blueprints namespace endpoints (`auth.login`, not `login`), and why every `url_for()` call in every template had to be updated in lockstep with the backend split
- Why CI needs a real database service container, not a mock, for an app whose bugs (so far) have consistently been at the SQL/type boundary
- That splitting a file is easy; splitting it *correctly* — deciding which module owns `get_budget_status()` when both the dashboard and the budgets page need it — is the actual design work

## Version 11 – Cloud Deployment and Operations

V10 made the codebase production-*ready* in isolation: tests, real migrations, CI. But the app had still only ever run on one laptop, through Flask's own development server, against a database on `localhost`. V11 is about actually running Mizan somewhere else — a real WSGI server, a database that isn't next to the app process, and the operational habits (health checks, environment-driven config) that a deployment needs.

### New Features (Operational, not user-facing)
- Gunicorn as the production WSGI server, replacing Flask's development server for anything other than local `python app.py` use
- `migrate.py`: migrations run as their own explicit step before the app starts, instead of at import time — so adding more Gunicorn workers later never risks every worker racing to apply migrations when it boots
- `blueprints/health.py`: an unauthenticated `GET /health` that a cloud platform's health checker can poll to tell whether an instance can actually serve requests, not just that the process is alive. It pings PostgreSQL and returns `503` if the database is unreachable, `200` otherwise — without ever including connection strings, hostnames, or raw SQL errors in the response

### Deployment Architecture

```
Browser
   ↓ HTTPS
Render Web Service
   ↓
Gunicorn
   ↓
Flask
   ↓
Render Private Network
   ↓
Render PostgreSQL
```

The web service and the database are separate managed resources on Render: Mizan doesn't run or manage its own database server, and when both are in the same account and region, the database is only reachable over Render's private network, not the public internet.

### Render Configuration

- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Pre-Deploy Command:** `python migrate.py`
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
- **Health Check Path:** `/health`

The Pre-Deploy Command runs after the build finishes and before the new version receives any traffic. If it fails — a bad migration, a database that's unreachable — the deploy stops there and the previous version keeps serving traffic, so Mizan is never left half-migrated and live at the same time. This requires a paid Render instance type; Render's free tier has no separate pre-deploy stage, so a free-tier deploy would need the migration folded into the build command instead.

Required environment variables, set directly in the Render dashboard and never committed to the repo:

```
DATABASE_URL          # Render's internal Postgres connection string
SECRET_KEY            # generated by Render, not chosen by hand
FLASK_ENV=production
FLASK_DEBUG=0
```

`DATABASE_URL` uses Render's *internal* connection string rather than the external one, since the web service and database live in the same Render account and region — internal traffic stays on Render's private network instead of round-tripping over the public internet.

### What I Learned
- That "the process is running" and "the app can serve a request" are different claims, and a health check earns its keep only by verifying the second one — `/health` is meaningful because it actually queries PostgreSQL, not because the Flask process merely responds
- That a bare `gunicorn app:app` isn't enough on a real platform: Gunicorn defaults to binding `127.0.0.1:8000`, which is invisible from outside its own container, so the start command has to bind explicitly to `0.0.0.0` and whatever port the platform assigns through `$PORT`
- Why a pre-deploy step is worth paying for: it turns "the migration failed" into "the deploy failed, the old version is still serving traffic," instead of "a worker crashed on boot" or, worse, "workers are running against half-migrated tables"
- Why `DATABASE_URL` should point at the internal network route rather than the public one when both services share a region — it's both faster and keeps database traffic off the public internet
- That environment-driven configuration is what actually makes "the same code, three environments" (local, CI, production) possible — nothing in the code branches on which environment it's running in beyond reading `FLASK_ENV`
## Version 13 – Transaction Data Pipeline and Monthly Insights

Every version up to V12 assumed transactions arrive one form submission at a time. V13 adds the other two directions — a CSV in and a CSV out — and changes what the dashboard means by "your money": not everything you have ever recorded, but this month.

### New Features
- Import transactions from a CSV file, with a preview of every row before anything is written
- Export transactions to CSV, honouring whatever filters the transactions page has applied
- An import history listing what each file added, skipped, and flagged, with a per-import summary
- A month-scoped dashboard summary: September Income, September Spending, September Net
- Five deterministic monthly insights: spending against last month, top category, average expense, largest expense, and budget utilisation

### The Import Flow

```text
Upload  →  Parse  →  Validate  →  Preview  →  Confirm  →  Summary
                                     ↑                       │
                              nothing written          one transaction
```

Uploading never writes. The preview shows every row with its normalised values and a status of valid, invalid, or duplicate, and confirming re-runs the entire pipeline over the original bytes rather than trusting what the browser was holding. The import itself is a single database transaction: the batch record, its transactions and its row errors all land together or none of them do.

Valid rows import even when others are invalid. A preview that reports "27 valid, 3 invalid" and then imports nothing would be a preview of nothing, and one typo on row 400 should not block 399 good rows.

### The CSV Contract

One format, `date,source,amount,type,category`, in that order:

```text
date,source,amount,type,category
2026-09-01,Carrefour,420.00,expense,Groceries
2026-09-02,Salary,12500.00,income,Salary
```

Header names are matched ignoring case and surrounding spaces, and extra columns are ignored. Anything more forgiving than that — guessing which column is the amount, parsing several date formats, stripping currency symbols — is column mapping, which V13 deliberately does not do. A row that would need it is reported as invalid so the file can be corrected, rather than silently interpreted.

### One Set of Validation Rules

The rules live in `services/transaction_rules.py`, with no Flask, no psycopg2 and no request context, and both entry points call them: the Add and Edit forms through a two-line adapter, and the importer per row. A row rejected by the importer would have been rejected by the form, and reports the same reason in the same words.

Extracting them was checked rather than assumed — the old and new validators were run against 115,500 combinations of adversarial field values, agreeing on all but the one deliberate change (a category now matches its canonical spelling case-insensitively, since a CSV supplies categories as free text where the forms use a `<select>`).

### Duplicate Protection

Re-importing a file you have already imported adds nothing. Detection compares a canonical key — user, date, source, amount, type and category — computed fresh for each import and never stored, so there is no derived column to migrate, backfill, or keep in step when a transaction is later edited.

Because the key only has to compare equal to another key, it can normalise harder than the values that actually get stored, which is what makes three real mismatches collapse:

- a row stored before V13 holding the doubled space someone typed, against a tidier CSV row
- a CSV amount of `419.999` against the `420.00` the `NUMERIC(12, 2)` column rounded it to
- `2026-9-1` against the `2026-09-01` the `DATE` column stores

The lookup is narrowed to the dates the file covers, so it is one indexed read rather than a scan of the account's history.

Detection is advisory, never a constraint. Two coffees at the same shop on the same day for the same price are a real pair of transactions, so the later row is flagged and skipped by default, with an explicit checkbox to import it anyway. A unique index would have made that second coffee permanently unrecordable — data loss wearing the costume of data hygiene.

### The Monthly Dashboard Change

Historical transactions are never deleted or reset. What changed is what the summary covers: the three headline figures are the current calendar month, and they roll over on their own when a new one starts. Everything earlier stays in the transactions list, the CSV export, and the multi-month trend chart — which is still whole-history, and is what demonstrates the summary discards nothing.

The third figure is **Net**, not Balance. It is one month's income minus that month's spending, and calling it a balance would misrepresent it the moment earlier months stopped contributing. Aggregates read as income, spending and net throughout; income and expense stay as the names of the two transaction types.

Where "this month" begins and ends now has one definition, `services/analytics.month_bounds()`, returning a half-open `[start, end)` range. Before V13 each caller worked it out separately, which is how the dashboard came to report all-time totals while the Budgets page reported monthly ones.

### Schema Changes

```text
0003  transactions (user_id, date) index      — backs every month-scoped query
0004  import_batches, import_row_errors       — what each import did, and why rows were skipped
      transactions.import_id                  — provenance, ON DELETE SET NULL
```

`import_id` is `SET NULL` rather than `CASCADE`: import history is a receipt, and throwing away a receipt must never throw away the money it describes.

`import_row_errors` stores a translation key rather than a rendered sentence, so an error recorded while the interface was in English still reads correctly in Arabic.

### Security

- Every import, export and history query is scoped to the session's user. Another account's import is a 404, not a 403 — confirming an id exists leaks more than refusing to discuss it.
- Uploads are bounded by a 2 MB request limit and a 2,000-row cap, and are read in memory: never written to disk, never executed. The `.csv` extension check is a courtesy to the user; the actual defence is that the bytes are only ever UTF-8 decoded and handed to a CSV reader.
- Filenames are reduced to a displayable string — directory components and unprintable characters removed, length bounded — rather than passed through `secure_filename`, which strips every non-ASCII character and would turn an Arabic filename into `csv`. Nothing here reaches a filesystem, so there is no path to traverse.
- Raw CSV is never stored. Only the derived rows, a SHA-256 of the upload for the repeated-file warning, and a truncated copy of any line that failed.
- CSRF, authentication, session cookie flags and account lockout are unchanged, and the new routes are covered by the same tests as the old ones.

### Demo Data

`scripts/seed_demo_data.py` builds a demo account with six months of history — around 195 transactions across every category, budgets sized so one is already over its limit, and two past imports so the history page has something to show.

```bash
python scripts/seed_demo_data.py   # username: admin, password: Demo12345!
```

Safe to re-run: it deletes the account and rebuilds it, so a rehearsal and the real thing show identical numbers.

Everything is anchored to calendar months rather than "days ago". The dashboard summary is month-scoped now, so a fixed day offset would land in a different month depending on when the script ran, and could leave the current month looking empty on stage. The current month is filled only as far as today — nothing is dated in the future, which would show up in the transactions list and skew the month-to-date figures.

The amounts are random but seeded, and the three largest one-offs are deliberate: without them the trend line is flat, which is honest about real spending and useless on a slide.

### What I Learned
- That a derived value is cheapest when it is not stored: dropping the fingerprint column removed a migration, a backfill, a drift risk between SQL and Python, and the question of what to do when an edited transaction's stored fingerprint goes stale — and cost one indexed query
- Why a duplicate check belongs in the interface rather than in a unique index: the database cannot tell an accidental double import from two identical coffees, and the one that guesses wrong deletes real data
- That "the preview said so" is not a fact the server may rely on — the page has been in the browser's hands, and the database may have changed underneath it, so confirming has to re-derive everything
- Why an audit record of a failed import has to be written in its own transaction: inside the batch it would roll back with everything else, leaving no trace; written carelessly afterwards it could claim rows that were never inserted
- That a half-written import is worse than a failed one, because a history row claiming transactions that are not there has to be reconciled by hand
- How much of bilingual support is bidirectional isolation rather than translation — a Latin filename or an ISO date dropped into an Arabic sentence reorders on screen unless it is isolated
- That running the code and reading the output catches what tests do not: two history columns both headed "Imported", an empty detail line under an average, and `secure_filename` quietly reducing an Arabic filename to `csv` were all found by looking, not by asserting
