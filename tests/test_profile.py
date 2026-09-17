import pytest

from tests.helpers import add_transaction, login, register, set_budget


@pytest.fixture(autouse=True)
def _logged_in(client):
    register(client)


def test_profile_shows_username_and_member_since(client):
    response = client.get("/profile")
    assert b"alice" in response.data
    assert b"Member since" in response.data


def test_change_password_wrong_current_rejected(client):
    response = client.post(
        "/profile/password",
        data={
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
            "confirm_new_password": "newpassword123",
        },
        follow_redirects=True,
    )
    assert b"Current password is incorrect" in response.data


def test_change_password_mismatch_rejected(client):
    response = client.post(
        "/profile/password",
        data={
            "current_password": "password123",
            "new_password": "newpassword123",
            "confirm_new_password": "different123",
        },
        follow_redirects=True,
    )
    assert b"do not match" in response.data


def test_change_password_same_as_current_rejected(client):
    response = client.post(
        "/profile/password",
        data={
            "current_password": "password123",
            "new_password": "password123",
            "confirm_new_password": "password123",
        },
        follow_redirects=True,
    )
    assert b"must be different" in response.data


def test_change_password_success_allows_relogin(client):
    response = client.post(
        "/profile/password",
        data={
            "current_password": "password123",
            "new_password": "newpassword123",
            "confirm_new_password": "newpassword123",
        },
        follow_redirects=True,
    )
    assert b"Password updated successfully" in response.data

    client.post("/logout")
    response = login(client, password="newpassword123")
    assert response.status_code == 200
    assert client.get("/").status_code == 200


def test_delete_account_wrong_password_rejected(client):
    response = client.post(
        "/profile/delete", data={"password": "wrongpassword"}, follow_redirects=True
    )
    assert b"Password is incorrect" in response.data
    assert client.get("/").status_code == 200  # still logged in


def test_delete_account_success_cascades_data(client):
    add_transaction(client)
    set_budget(client)

    response = client.post(
        "/profile/delete", data={"password": "password123"}, follow_redirects=True
    )
    assert b"Your account has been deleted" in response.data

    # session cleared -> redirected to login for any protected page
    assert client.get("/", follow_redirects=False).status_code == 302

    # re-registering the same username succeeds, proving the old row (and its
    # data) is really gone, not just hidden
    response = register(client)
    assert response.status_code == 200
    assert b"Test Store" not in client.get("/transactions").data


def test_language_switch_persists_for_logged_in_user(client):
    client.post("/language/ar")
    client.post("/logout")
    response = login(client)
    assert response.status_code == 200
    assert b'dir="rtl"' in client.get("/").data
