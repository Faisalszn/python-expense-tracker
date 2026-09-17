from tests.helpers import login, register


def test_anonymous_visitor_redirected_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_register_creates_account_and_logs_in(client):
    response = register(client)
    assert response.status_code == 200
    assert client.get("/").status_code == 200


def test_register_duplicate_username_rejected(client):
    register(client, username="alice")
    client.post("/logout")
    response = register(client, username="alice")
    assert response.status_code == 400
    assert b"already taken" in response.data


def test_register_short_password_rejected(client):
    response = client.post(
        "/register",
        data={"username": "alice", "password": "short", "confirm_password": "short"},
    )
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data


def test_register_password_mismatch_rejected(client):
    response = client.post(
        "/register",
        data={
            "username": "alice",
            "password": "password123",
            "confirm_password": "different123",
        },
    )
    assert response.status_code == 400
    assert b"do not match" in response.data


def test_login_wrong_password_rejected(client):
    register(client)
    client.post("/logout")
    response = login(client, password="wrongpassword")
    assert response.status_code == 400
    assert b"Invalid username or password" in response.data


def test_login_unknown_user_rejected(client):
    response = login(client, username="nobody")
    assert response.status_code == 400
    assert b"Invalid username or password" in response.data


def test_logout_clears_session(client):
    register(client)
    client.post("/logout")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
