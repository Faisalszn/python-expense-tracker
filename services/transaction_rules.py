"""Transaction field rules, shared by every entry path.

Manual entry (the Add/Edit forms) and, from V13 on, CSV import both need the
same answer to "is this a valid transaction, and what exactly gets stored?".
Keeping that answer in one module — with no Flask, no psycopg2, and no request
context — means there is one definition to change rather than one per caller.

Validation stops at the first problem and reports it as a translation key, so
callers stay free to render it however suits them: a flash message for the
forms, a per-row cell in the CSV import preview.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from constants import CATEGORIES

TRANSACTION_FIELDS = ("date", "source", "amount", "type", "category")

TRANSACTION_TYPES = ("income", "expense")

DATE_FORMAT = "%Y-%m-%d"

# Canonical category keyed by its case-folded form. Categories arrive from a
# <select> on the web forms, so they are already canonical there, but a CSV
# supplies them as free text where "groceries" is plainly the same category as
# "Groceries". Matching is case-insensitive and nothing more: no aliases, no
# fuzzy matching, no inference, no categories beyond constants.CATEGORIES.
CANONICAL_CATEGORIES = {category.casefold(): category for category in CATEGORIES}


def _field(raw, name):
    """Read one field as a trimmed string, tolerating missing or None values."""
    # csv.DictReader gives None for columns a short row never reached, so this
    # cannot assume every field is present as a string the way a form does.
    value = raw.get(name)
    return value.strip() if isinstance(value, str) else ""


def normalize_and_validate(raw):
    """Normalize and validate one transaction, returning a (data, error_key) tuple.

    `raw` is any mapping of the five transaction fields to strings: a Werkzeug
    form, a csv.DictReader row, or a plain dict. Exactly one half of the
    returned tuple is ever set.

    The checks run in a fixed order and the first failure wins, so a row with
    two problems always reports the same one.
    """
    category = CANONICAL_CATEGORIES.get(_field(raw, "category").casefold())
    if category is None:
        return None, "error.invalid_category"

    date = _field(raw, "date")
    if not date:
        return None, "error.date_required"
    try:
        datetime.strptime(date, DATE_FORMAT)
    except ValueError:
        return None, "error.invalid_date_format"

    source = _field(raw, "source")
    if not source:
        return None, "error.source_required"
    if source.isdigit():
        return None, "error.source_numeric"

    try:
        amount = Decimal(_field(raw, "amount"))
    except InvalidOperation:
        return None, "error.amount_not_number"
    # Decimal, unlike float(), accepts "NaN" and "Infinity" as valid input, and
    # PostgreSQL sorts NUMERIC 'NaN' above every real number — so the `<= 0`
    # check below would let both straight through without this guard.
    if not amount.is_finite():
        return None, "error.amount_not_number"
    if amount <= 0:
        return None, "error.amount_not_positive"

    transaction_type = _field(raw, "type").lower()
    if transaction_type not in TRANSACTION_TYPES:
        return None, "error.invalid_transaction_type"

    return {
        "date": date,
        "source": source,
        "amount": amount,
        "type": transaction_type,
        "category": category,
    }, None
