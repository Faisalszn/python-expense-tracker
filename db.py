"""Database connection and migration runner.

Migrations live as plain .sql files in migrations/, named with a numeric
prefix (0001_..., 0002_...). Each one runs at most once per database; the
applied set is tracked in a schema_migrations table. Files are written to
be safe to run against either a brand-new database or one that already has
these tables/columns/types, since a personal project like this one doesn't
have a fixed "starting point" everyone upgrades from.
"""

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Loaded here, not just in app.py: this module reads DATABASE_URL from the
# environment at import time, and other modules import it (transitively,
# via the blueprints) before app.py's own load_dotenv() call would run.
load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/expense_tracker"
)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@contextmanager
def get_connection():
    """Yield a psycopg2 connection and guarantee it's closed afterward."""
    connection = psycopg2.connect(DATABASE_URL)
    try:
        yield connection
    finally:
        connection.close()


def run_migrations():
    """Apply any migration files that haven't been recorded as applied yet."""
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT now()
            )
        """)
        connection.commit()

        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in applied:
                continue

            cursor.execute(path.read_text())
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )
            connection.commit()
