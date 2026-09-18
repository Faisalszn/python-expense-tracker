"""Applies any pending database migrations. Run before starting Gunicorn.

    python migrate.py
    gunicorn app:app
"""

from db import run_migrations

if __name__ == "__main__":
    run_migrations()
