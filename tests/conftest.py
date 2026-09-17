"""Shared pytest fixtures.

Tests run against a real PostgreSQL database (TEST_DATABASE_URL, falling
back to a local default) rather than mocks, so they exercise the same SQL
and type behavior the app relies on in production. Every table is
truncated before each test for isolation.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://app_user:app_password@localhost:5432/expense_tracker_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest

import db
from app import create_app


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    db.run_migrations()


@pytest.fixture(autouse=True)
def _clean_database():
    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("TRUNCATE users, transactions, budgets RESTART IDENTITY CASCADE")
        connection.commit()
    yield


@pytest.fixture()
def app():
    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
