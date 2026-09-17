import re

from app import create_app
from tests.helpers import add_transaction, login, register, set_budget


def test_lockout_after_five_failed_attempts(client):
    register(client)
    client.post("/logout")

    for _ in range(5):
        response = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert response.status_code == 400

    response = client.post("/login", data={"username": "alice", "password": "password123"})
    assert response.status_code == 429
    assert b"Too many failed attempts" in response.data


def test_successful_login_resets_lockout_counter(client):
    register(client)
    client.post("/logout")

    for _ in range(3):
        client.post("/login", data={"username": "alice", "password": "wrong"})

    login(client)
    client.post("/logout")

    for _ in range(3):
        response = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert response.status_code == 400  # not locked: counter reset by the success above


def test_user_cannot_view_or_edit_other_users_transaction(client):
    register(client, username="alice")
    add_transaction(client)
    match = re.search(rb"<td>(\d+)</td>", client.get("/transactions").data)
    transaction_id = match.group(1).decode()
    client.post("/logout")

    register(client, username="bob")
    response = client.get(f"/transactions/{transaction_id}/edit")
    assert response.status_code == 404


def test_user_cannot_delete_other_users_transaction(client):
    register(client, username="alice")
    add_transaction(client, source="Alice Only")
    match = re.search(rb"<td>(\d+)</td>", client.get("/transactions").data)
    transaction_id = match.group(1).decode()
    client.post("/logout")

    register(client, username="bob")
    client.post(f"/transactions/{transaction_id}/delete", follow_redirects=True)

    client.post("/logout")
    login(client, username="alice")
    assert b"Alice Only" in client.get("/transactions").data


def test_user_cannot_delete_other_users_budget(client):
    register(client, username="alice")
    set_budget(client, category="Groceries", monthly_limit="200")
    client.post("/logout")

    register(client, username="bob")
    client.post("/budgets/Groceries/delete", follow_redirects=True)

    client.post("/logout")
    login(client, username="alice")
    assert b"200.00" in client.get("/budgets").data


def test_csrf_rejects_post_without_token():
    csrf_app = create_app()
    csrf_app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    client = csrf_app.test_client()

    response = client.post(
        "/register",
        data={"username": "alice", "password": "password123", "confirm_password": "password123"},
    )
    assert response.status_code == 400


def test_csrf_accepts_post_with_real_token():
    csrf_app = create_app()
    csrf_app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    client = csrf_app.test_client()

    get_response = client.get("/register")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', get_response.data).group(1).decode()

    response = client.post(
        "/register",
        data={
            "username": "alice",
            "password": "password123",
            "confirm_password": "password123",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
