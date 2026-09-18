import psycopg2
from flask import Blueprint, jsonify

from db import get_connection

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    try:
        with get_connection() as connection:
            connection.cursor().execute("SELECT 1")
    except psycopg2.Error:
        return jsonify(status="error", database="unreachable"), 503

    return jsonify(status="ok", database="connected")
