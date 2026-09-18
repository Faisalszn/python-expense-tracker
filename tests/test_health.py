import db


def test_health_reports_ok_when_database_reachable(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "connected"}


def test_health_reports_503_when_database_unreachable(client, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "postgresql://localhost:1/nonexistent")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "database": "unreachable"}


def test_health_does_not_require_login(client):
    assert client.get("/").status_code == 302  # every other route redirects when logged out
    assert client.get("/health").status_code == 200
