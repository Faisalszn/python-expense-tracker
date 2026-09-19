"""Transaction field rules, shared by every entry path.

Manual entry (the Add/Edit forms) and, from V13 on, CSV import both need the
same answer to "is this a valid transaction, and what exactly gets stored?".
Keeping that answer in one module — with no Flask, no psycopg2, and no request
context — means there is one definition to change rather than one per caller.

Validation stops at the first problem and reports it as a translation key, so
callers stay free to render it however suits them: a flash message for the
forms, a per-row cell in the CSV import preview.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from constants import CATEGORIES

TRANSACTION_FIELDS = ("date", "source", "amount", "type", "category")

TRANSACTION_TYPES = ("income", "expense")

DATE_FORMAT = "%Y-%m-%d"

# ASCII unit separator: joins the parts of a comparison key. A validated source
# is printable text, so it can never contain one and shift the boundary between
# two fields.
SEPARATOR = "\x1f"

_CENTS = Decimal("0.01")

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


def parse_date(value):
    """Return a date object for an already-validated date value."""
    if isinstance(value, date):
        return value
    return datetime.strptime(value.strip(), DATE_FORMAT).date()


def canonical_key(user_id, transaction):
    """Return a comparison key identifying one transaction's content.

    Used to spot a row that has already been recorded. The key is computed
    fresh every time and never stored, which is what lets it normalize harder
    than the values that do get stored: a key only has to compare equal to
    another key, so folding case and whitespace here costs nothing and cannot
    rewrite anyone's data.

    That extra folding is load-bearing in both directions:

    - a stored row predating V13 may hold "Carrefour  Mall" with the doubled
      space the user typed, and must still match a tidier CSV row
    - a CSV amount of "19.999" must match the "20.00" the NUMERIC(12, 2)
      column rounded it to, and "2026-9-1" the DATE column's 2026-09-01

    Duplicate detection is advisory, so this is a convenience, never a
    security boundary: queries are scoped with `WHERE user_id = %s`, and
    including the id here does not change that.
    """
    amount = Decimal(transaction["amount"]).quantize(_CENTS, ROUND_HALF_UP)

    return SEPARATOR.join((
        str(user_id),
        parse_date(transaction["date"]).isoformat(),
        " ".join(transaction["source"].split()).casefold(),
        f"{amount:f}",
        transaction["type"],
        transaction["category"],
    ))
