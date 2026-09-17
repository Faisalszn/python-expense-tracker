from datetime import datetime, timedelta
from functools import wraps
from math import ceil

import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, session
from psycopg2 import errorcodes
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_connection
from i18n import t
from translations import DEFAULT_LANGUAGE

auth_bp = Blueprint("auth", __name__)

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_LOCKOUT_MINUTES = 15


def login_required(view):
    """Redirect anonymous visitors to the login page before running a view."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash(t("error.login_required"))
            return redirect("/login")
        return view(*args, **kwargs)

    return wrapped_view


def validate_credentials(username, password):
    """Validate a username/password pair, returning an error key or None."""
    if not username:
        return "error.username_required"
    if len(password) < 8:
        return "error.password_too_short"
    return None


def get_user_by_username(username):
    """Return (id, password_hash, language, failed_login_attempts, locked_until)."""
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, password_hash, language, failed_login_attempts, locked_until
                FROM users
                WHERE username = %s
                """,
                (username,)
            )
            return cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return None


def record_failed_login(user_id, failed_attempts):
    """Increment the failed-attempt counter, locking the account past the limit."""
    new_attempts = failed_attempts + 1
    locked_until = None
    if new_attempts >= LOGIN_ATTEMPT_LIMIT:
        locked_until = datetime.now() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
        new_attempts = 0

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET failed_login_attempts = %s, locked_until = %s WHERE id = %s",
                (new_attempts, locked_until, user_id)
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))


def record_successful_login(user_id):
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
                (user_id,)
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        error = validate_credentials(username, password)
        if not error and password != confirm_password:
            error = "error.passwords_mismatch"

        if error:
            flash(t(error))
            return render_template("register.html"), 400

        # pbkdf2 avoids relying on hashlib.scrypt, which isn't available on
        # Python builds linked against LibreSSL instead of OpenSSL (e.g. macOS's
        # system Python).
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, language)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (username, password_hash, session.get("language", DEFAULT_LANGUAGE))
                )
                user_id = cursor.fetchone()[0]
                connection.commit()
        except psycopg2.IntegrityError as e:
            if e.pgcode == errorcodes.UNIQUE_VIOLATION:
                flash(t("error.username_taken"))
            else:
                flash(t("error.database", error=e))
            return render_template("register.html"), 400
        except psycopg2.Error as e:
            flash(t("error.database", error=e))
            return render_template("register.html"), 500

        session["user_id"] = user_id
        session["username"] = username
        return redirect("/")

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if user is not None:
            user_id, password_hash, language, failed_attempts, locked_until = user

            if locked_until is not None and locked_until > datetime.now():
                minutes_left = ceil((locked_until - datetime.now()).total_seconds() / 60)
                flash(t("error.account_locked", minutes=minutes_left))
                return render_template("login.html"), 429

            if check_password_hash(password_hash, password):
                record_successful_login(user_id)
                session["user_id"] = user_id
                session["username"] = username
                session["language"] = language or DEFAULT_LANGUAGE
                return redirect("/")

            record_failed_login(user_id, failed_attempts)

        flash(t("error.invalid_login"))
        return render_template("login.html"), 400

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")
