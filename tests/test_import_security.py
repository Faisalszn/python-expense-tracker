"""Security properties of the import and export flow.

Mostly assertions that the boring, easily-forgotten protections are actually
in place on the routes V13 added, rather than only on the ones that had them
before.
"""

import io
import re

import pytest

import db
from app import create_app
from tests.helpers import add_transaction, register

HEADER = "date,source,amount,type,category"
ROW = "2026-09-01,Carrefour,420.00,expense,Groceries"


def transaction_count():
    with db.get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT count(*) FROM transactions")
        return cursor.fetchone()[0]


# --- CSRF ---------------------------------------------------------------------


@pytest.fixture()
def csrf_client():
    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    return application.test_client()


def token_from(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data).group(1).decode()


def register_with_csrf(client):
    token = token_from(client.get("/register"))
    client.post(
        "/register",
        data={
            "username": "alice",
            "password": "password123",
            "confirm_password": "password123",
            "csrf_token": token,
        },
        follow_redirects=True,
    )


def test_upload_without_a_csrf_token_is_rejected(csrf_client):
    register_with_csrf(csrf_client)

    response = csrf_client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(f"{HEADER}\n{ROW}".encode()), "x.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_confirm_without_a_csrf_token_is_rejected(csrf_client):
    register_with_csrf(csrf_client)

    response = csrf_client.post(
        "/transactions/import/confirm", data={"payload": "", "filename": "x.csv"}
    )

    assert response.status_code == 400
    assert transaction_count() == 0


def test_the_upload_form_carries_a_csrf_token(csrf_client):
    register_with_csrf(csrf_client)

    assert b'name="csrf_token"' in csrf_client.get("/transactions/import").data


def test_a_real_token_lets_an_upload_through(csrf_client):
    register_with_csrf(csrf_client)
    token = token_from(csrf_client.get("/transactions/import"))

    response = csrf_client.post(
        "/transactions/import/preview",
        data={
            "file": (io.BytesIO(f"{HEADER}\n{ROW}".encode()), "x.csv"),
            "csrf_token": token,
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200


# --- authentication on every new route ---------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/transactions/import"),
        ("post", "/transactions/import/preview"),
        ("post", "/transactions/import/confirm"),
        ("get", "/transactions/imports"),
        ("get", "/transactions/imports/1"),
        ("get", "/transactions/export.csv"),
    ],
)
def test_every_import_route_requires_a_login(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# --- the upload size limit ----------------------------------------------------


def test_an_oversized_upload_never_reaches_the_parser(client, app):
    register(client)
    oversized = b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1024)

    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(oversized), "huge.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert transaction_count() == 0


def test_an_oversized_post_elsewhere_does_not_show_the_import_page(client):
    # A registration that overruns the limit should not be answered with an
    # upload form, least of all to somebody who is not logged in.
    response = client.post("/register", data={"username": "a" * 3_000_000})

    assert response.status_code == 413
    assert b"Expected format" not in response.data
    assert b"too large" in response.data


def test_an_oversized_upload_from_a_logged_out_visitor_goes_to_login(client, app):
    oversized = b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1024)

    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(oversized), "huge.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302


# --- uploaded content is never trusted ---------------------------------------


def test_an_uploaded_file_is_never_written_to_disk(client, tmp_path, monkeypatch):
    register(client)
    monkeypatch.chdir(tmp_path)

    client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(f"{HEADER}\n{ROW}".encode()), "x.csv")},
        content_type="multipart/form-data",
    )

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "hostile",
    [
        "=1+1",
        "=HYPERLINK(\"http://evil\",\"click\")",
        "<script>alert(1)</script>",
        "'; DROP TABLE transactions; --",
        "{{ 7*7 }}",
    ],
)
def test_hostile_source_values_are_stored_as_text_and_escaped(client, hostile):
    register(client)
    row = f"2026-09-01,\"{hostile}\",10.00,expense,Bills"

    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(f"{HEADER}\n{row}".encode()), "x.csv")},
        content_type="multipart/form-data",
    )
    body = response.data.decode()

    # Rendered as text, never as markup, and never evaluated as a template.
    assert hostile not in body or "<" not in hostile
    assert "49" not in body  # {{ 7*7 }} was not evaluated
    assert transaction_count() == 0  # and the preview still wrote nothing


def test_sql_in_a_csv_cell_does_not_reach_the_database_as_sql(client):
    register(client)
    add_transaction(client, source="Survivor")
    row = "2026-09-01,'); DROP TABLE transactions; --,10.00,expense,Bills"

    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(f"{HEADER}\n{row}".encode()), "x.csv")},
        content_type="multipart/form-data",
    )
    html = response.data.decode()
    payload = re.search(r'name="payload" value="([^"]*)"', html).group(1)
    filename = re.search(r'name="filename" value="([^"]*)"', html).group(1)
    client.post(
        "/transactions/import/confirm",
        data={"payload": payload, "filename": filename},
        follow_redirects=True,
    )

    # The table is still there, and the cell was stored as an ordinary source.
    assert b"Survivor" in client.get("/transactions").data
    assert transaction_count() == 2


# --- exported data stays the owner's -----------------------------------------


def test_export_never_includes_another_users_rows(client):
    register(client, username="alice")
    add_transaction(client, source="Alice Only")
    client.post("/logout")

    register(client, username="bob")
    exported = client.get("/transactions/export.csv").data

    assert b"Alice Only" not in exported
