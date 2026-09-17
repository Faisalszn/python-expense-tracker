import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from blueprints.auth import login_required, validate_credentials
from db import get_connection
from i18n import t
from translations import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile")
@login_required
def profile():
    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT username, created_at, language FROM users WHERE id = %s",
                (session["user_id"],)
            )
            user = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        user = None

    return render_template(
        "profile.html",
        username=user[0] if user else session.get("username"),
        member_since=user[1] if user else None,
        languages=SUPPORTED_LANGUAGES
    )


@profile_bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new_password = request.form.get("confirm_new_password", "")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (session["user_id"],)
            )
            row = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    if row is None or not check_password_hash(row[0], current_password):
        flash(t("error.current_password_incorrect"))
        return redirect("/profile")

    error = validate_credentials(session.get("username", ""), new_password)
    if not error and new_password != confirm_new_password:
        error = "error.passwords_mismatch"
    if not error and check_password_hash(row[0], new_password):
        error = "error.new_password_same"

    if error:
        flash(t(error))
        return redirect("/profile")

    new_password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_password_hash, session["user_id"])
            )
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    flash(t("success.password_changed"))
    return redirect("/profile")


@profile_bp.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (session["user_id"],)
            )
            row = cursor.fetchone()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    if row is None or not check_password_hash(row[0], password):
        flash(t("error.delete_password_incorrect"))
        return redirect("/profile")

    try:
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (session["user_id"],))
            connection.commit()
    except psycopg2.Error as e:
        flash(t("error.database", error=e))
        return redirect("/profile")

    session.clear()
    flash(t("success.account_deleted"))
    return redirect("/login")


@profile_bp.route("/language/<lang>", methods=["POST"])
def set_language(lang):
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    session["language"] = lang

    if "user_id" in session:
        try:
            with get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "UPDATE users SET language = %s WHERE id = %s",
                    (lang, session["user_id"])
                )
                connection.commit()
        except psycopg2.Error as e:
            flash(t("error.database", error=e))

    return redirect(request.referrer or "/")
