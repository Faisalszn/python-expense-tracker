"""Small helpers shared across test modules."""


def register(client, username="alice", password="password123"):
    return client.post(
        "/register",
        data={"username": username, "password": password, "confirm_password": password},
        follow_redirects=True,
    )


def login(client, username="alice", password="password123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def add_transaction(client, **overrides):
    data = {
        "date": "2026-09-01",
        "source": "Test Store",
        "amount": "42.50",
        "type": "expense",
        "category": "Groceries",
    }
    data.update(overrides)
    return client.post("/transactions/add", data=data, follow_redirects=True)


def set_budget(client, category="Groceries", monthly_limit="200"):
    return client.post(
        "/budgets",
        data={"category": category, "monthly_limit": monthly_limit},
        follow_redirects=True,
    )
