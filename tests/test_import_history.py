"""The list of past imports.

Ownership is the thing to get right here: an import record names a file and
counts a user's transactions, so one account must never see another's.
"""

import io
import re

import pytest

from tests.helpers import login, register

HEADER = "date,source,amount,type,category"
ROW_A = "2026-09-01,Carrefour,420.00,expense,Groceries"
ROW_B = "2026-09-02,Salary,12500.00,income,Salary"
BAD_ROW = "not-a-date,Broken,10.00,expense,Bills"


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def import_csv(client, text, filename="september.csv"):
    response = client.post(
        "/transactions/import/preview",
        data={"file": (io.BytesIO(text.encode()), filename)},
        content_type="multipart/form-data",
    )
    html = response.data.decode()
    return client.post(
        "/transactions/import/confirm",
        data={
            "payload": re.search(r'name="payload" value="([^"]*)"', html).group(1),
            "filename": re.search(r'name="filename" value="([^"]*)"', html).group(1),
        },
        follow_redirects=True,
    )


def history(client):
    return client.get("/transactions/imports")


def listed_files(client):
    """Filenames in the history table, in the order shown."""
    html = history(client).data.decode()
    if "<tbody>" not in html:
        return []
    body = html[html.index("<tbody>"):html.index("</tbody>")]
    return re.findall(r'<a href="/transactions/imports/\d+">([^<]+)</a>', body)


# --- the list -----------------------------------------------------------------


def test_history_is_empty_before_any_import(client):
    response = history(client)

    assert response.status_code == 200
    assert b"No imports yet" in response.data


def test_an_import_appears_in_the_history(client):
    import_csv(client, f"{HEADER}\n{ROW_A}", filename="september.csv")

    assert listed_files(client) == ["september.csv"]


def test_imports_are_listed_newest_first(client):
    import_csv(client, f"{HEADER}\n{ROW_A}", filename="first.csv")
    import_csv(client, f"{HEADER}\n{ROW_B}", filename="second.csv")

    assert listed_files(client) == ["second.csv", "first.csv"]


def test_history_shows_what_each_import_did(client):
    import_csv(client, f"{HEADER}\n{ROW_A}\n{BAD_ROW}\n{ROW_B}")

    html = history(client).data.decode()
    row = html[html.index("<tbody>"):html.index("</tbody>")]

    assert ">2<" in row       # imported
    assert ">1<" in row       # skipped
    assert "Partial" in row


def test_a_clean_import_is_marked_completed(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")

    assert b"Completed" in history(client).data


def test_each_entry_links_to_its_summary(client):
    import_csv(client, f"{HEADER}\n{ROW_A}")

    link = re.search(rb'href="(/transactions/imports/\d+)"', history(client).data).group(1)
    detail = client.get(link.decode())

    assert detail.status_code == 200
    assert b"Import Complete" in detail.data


def test_a_non_ascii_filename_is_listed_intact(client):
    import_csv(client, f"{HEADER}\n{ROW_A}", filename="ميزانية.csv")

    assert listed_files(client) == ["ميزانية.csv"]


# --- ownership ----------------------------------------------------------------


def test_history_only_shows_the_logged_in_users_imports(client):
    import_csv(client, f"{HEADER}\n{ROW_A}", filename="alice.csv")
    client.post("/logout")

    register(client, username="bob")
    assert listed_files(client) == []
    assert b"alice.csv" not in history(client).data

    import_csv(client, f"{HEADER}\n{ROW_B}", filename="bob.csv")
    assert listed_files(client) == ["bob.csv"]

    client.post("/logout")
    login(client)
    assert listed_files(client) == ["alice.csv"]


def test_history_requires_a_login(client):
    client.post("/logout")

    response = history(client)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# --- reachability -------------------------------------------------------------


def test_history_is_reachable_from_the_import_page(client):
    assert b"/transactions/imports" in client.get("/transactions/import").data


def test_history_is_reachable_from_an_import_summary(client):
    response = import_csv(client, f"{HEADER}\n{ROW_A}")

    assert b'href="/transactions/imports"' in response.data
