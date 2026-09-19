import os

from flask import Flask
from flask_wtf import CSRFProtect

from blueprints.auth import auth_bp
from blueprints.budgets import budgets_bp
from blueprints.dashboard import dashboard_bp
from blueprints.health import health_bp
from blueprints.imports import imports_bp, render_upload_form
from blueprints.profile import profile_bp
from blueprints.transactions import transactions_bp
from i18n import register_i18n


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev")  # set SECRET_KEY in production

    if os.environ.get("FLASK_ENV") == "production" and app.secret_key == "dev":
        raise RuntimeError(
            "SECRET_KEY must be set via environment variable when FLASK_ENV=production"
        )

    app.config.update(
        # Bounds every request body, uploads included. Comfortably above the
        # largest file the importer will accept (MAX_IMPORT_ROWS rows of
        # canonical CSV) and far below anything that could exhaust memory.
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
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
    app.register_blueprint(imports_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(health_bp)

    @app.errorhandler(413)
    def payload_too_large(error):
        # Werkzeug's own 413 page says nothing a person can act on.
        megabytes = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_upload_form(size_error=megabytes), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
