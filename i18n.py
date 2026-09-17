"""Shared translation helper, used by every blueprint and by templates."""

from flask import session

from translations import DEFAULT_LANGUAGE, translate


def t(key, **kwargs):
    """Translate `key` into the current session's language."""
    return translate(key, session.get("language", DEFAULT_LANGUAGE), **kwargs)


def register_i18n(app):
    @app.context_processor
    def inject_i18n():
        lang = session.get("language", DEFAULT_LANGUAGE)
        return {
            "t": t,
            "lang": lang,
            "text_dir": "rtl" if lang == "ar" else "ltr",
        }
