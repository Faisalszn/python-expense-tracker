import os

from flask import Flask
from flask_wtf import CSRFProtect

from blueprints.auth import auth_bp
from blueprints.budgets import budgets_bp
from blueprints.dashboard import dashboard_bp
from blueprints.profile import profile_bp
from blueprints.transactions import transactions_bp
from db import run_migrations  # also loads .env, before any other module reads it
from i18n import register_i18n


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev")  # set SECRET_KEY in production

    if os.environ.get("FLASK_ENV") == "production" and app.secret_key == "dev":
        raise RuntimeError(
            "SECRET_KEY must be set via environment variable when FLASK_ENV=production"
        )

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Only require HTTPS-only cookies once the app is actually served over HTTPS.
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    )

    CSRFProtect(app)
    register_i18n(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(budgets_bp)

    return app


app = create_app()
run_migrations()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
