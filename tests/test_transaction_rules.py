"""Unit tests for the shared transaction rules.

These exercise services.transaction_rules directly rather than through a
route: the module is deliberately free of Flask and psycopg2, and testing it
that way is what keeps it that way. Route-level behavior stays covered by
tests/test_transactions.py.
"""

from decimal import Decimal

import pytest

from constants import CATEGORIES
from services.transaction_rules import normalize_and_validate

VALID = {
    "date": "2026-09-01",
    "source": "Carrefour",
    "amount": "420.00",
    "type": "expense",
    "category": "Groceries",
}


def build(**overrides):
    return {**VALID, **overrides}


def test_valid_transaction_returns_data_and_no_error():
    data, error = normalize_and_validate(VALID)
    assert error is None
    assert data == {
        "date": "2026-09-01",
        "source": "Carrefour",
        "amount": Decimal("420.00"),
        "type": "expense",
        "category": "Groceries",
    }


def test_returns_exactly_the_five_transaction_fields():
    data, _ = normalize_and_validate(VALID)
    assert set(data) == {"date", "source", "amount", "type", "category"}


# --- category: trim + case-insensitive match, nothing more -------------------


@pytest.mark.parametrize("supplied", ["Groceries", "groceries", "GROCERIES", "gRoCeRiEs"])
def test_category_matches_case_insensitively(supplied):
    data, error = normalize_and_validate(build(category=supplied))
    assert error is None
    assert data["category"] == "Groceries"


def test_category_surrounding_whitespace_trimmed():
    data, error = normalize_and_validate(build(category="  Dining  "))
    assert error is None
    assert data["category"] == "Dining"


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_canonical_category_round_trips_from_lowercase(category):
    data, error = normalize_and_validate(build(category=category.lower()))
    assert error is None
    assert data["category"] == category


@pytest.mark.parametrize("supplied", ["", "   ", "NotACategory", "Food", "Grocery", "Groceries!"])
def test_unknown_category_rejected(supplied):
    # "Food"/"Grocery" specifically: no aliases, no fuzzy or prefix matching.
    assert normalize_and_validate(build(category=supplied)) == (None, "error.invalid_category")


def test_category_normalization_never_invents_a_category():
    data, _ = normalize_and_validate(build(category="other"))
    assert data["category"] in CATEGORIES


# --- date --------------------------------------------------------------------


@pytest.mark.parametrize("supplied", ["", "   "])
def test_missing_date_rejected(supplied):
    assert normalize_and_validate(build(date=supplied)) == (None, "error.date_required")


@pytest.mark.parametrize(
    "supplied", ["not-a-date", "2026-13-40", "2026-02-30", "01/09/2026", "20260901", "2026-09-01x"]
)
def test_invalid_date_rejected(supplied):
    assert normalize_and_validate(build(date=supplied)) == (None, "error.invalid_date_format")


def test_unpadded_date_accepted_as_before():
    # Pre-existing behavior, preserved deliberately: strptime("%Y-%m-%d")
    # accepts unpadded months and days, and PostgreSQL's DATE column stores
    # "2026-9-1" as 2026-09-01. Rejecting it would be a behavior change, which
    # this phase does not make.
    data, error = normalize_and_validate(build(date="2026-9-1"))
    assert error is None
    assert data["date"] == "2026-9-1"


def test_date_surrounding_whitespace_trimmed():
    data, error = normalize_and_validate(build(date="  2026-09-01  "))
    assert error is None
    assert data["date"] == "2026-09-01"


def test_leap_day_accepted():
    data, error = normalize_and_validate(build(date="2028-02-29"))
    assert error is None
    assert data["date"] == "2028-02-29"


# --- source ------------------------------------------------------------------


@pytest.mark.parametrize("supplied", ["", "   "])
def test_missing_source_rejected(supplied):
    assert normalize_and_validate(build(source=supplied)) == (None, "error.source_required")


@pytest.mark.parametrize("supplied", ["12345", "0"])
def test_numeric_only_source_rejected(supplied):
    assert normalize_and_validate(build(source=supplied)) == (None, "error.source_numeric")


def test_source_surrounding_whitespace_trimmed():
    data, error = normalize_and_validate(build(source="  Carrefour  "))
    assert error is None
    assert data["source"] == "Carrefour"


def test_source_internal_whitespace_preserved():
    # V13 deliberately does not collapse internal whitespace on the value that
    # gets stored: that would silently rewrite what the user typed.
    data, error = normalize_and_validate(build(source="Carrefour  City  Mall"))
    assert error is None
    assert data["source"] == "Carrefour  City  Mall"


def test_source_with_digits_accepted_when_not_entirely_numeric():
    data, error = normalize_and_validate(build(source="7Eleven"))
    assert error is None
    assert data["source"] == "7Eleven"


def test_long_source_accepted():
    # No source-length rule exists in the app or the schema, and V13 does not
    # introduce one.
    long_source = "A" * 500
    data, error = normalize_and_validate(build(source=long_source))
    assert error is None
    assert data["source"] == long_source


# --- amount ------------------------------------------------------------------


@pytest.mark.parametrize("supplied", ["", "   ", "abc", "1,234.56", "12.34.56", "12 34"])
def test_non_numeric_amount_rejected(supplied):
    assert normalize_and_validate(build(amount=supplied)) == (None, "error.amount_not_number")


@pytest.mark.parametrize("supplied", ["NaN", "-NaN", "sNaN", "Infinity", "-Infinity", "inf"])
def test_non_finite_amount_rejected(supplied):
    # Decimal() accepts all of these where float() would too; PostgreSQL then
    # sorts NUMERIC 'NaN' above every real number, so `> 0` alone is not enough.
    assert normalize_and_validate(build(amount=supplied)) == (None, "error.amount_not_number")


@pytest.mark.parametrize("supplied", ["0", "0.00", "-5", "-0.01"])
def test_non_positive_amount_rejected(supplied):
    assert normalize_and_validate(build(amount=supplied)) == (None, "error.amount_not_positive")


def test_amount_returned_as_decimal_without_rounding():
    # Rounding to the column's 2 decimal places stays PostgreSQL's job, exactly
    # as it was before the rules moved into this module.
    data, error = normalize_and_validate(build(amount="19.999"))
    assert error is None
    assert data["amount"] == Decimal("19.999")


def test_amount_surrounding_whitespace_trimmed():
    data, error = normalize_and_validate(build(amount="  42.50  "))
    assert error is None
    assert data["amount"] == Decimal("42.50")


# --- type --------------------------------------------------------------------


@pytest.mark.parametrize("supplied", ["income", "INCOME", "  Income  "])
def test_type_case_and_whitespace_normalized(supplied):
    data, error = normalize_and_validate(build(type=supplied))
    assert error is None
    assert data["type"] == "income"


@pytest.mark.parametrize("supplied", ["", "   ", "transfer", "expenses", "in"])
def test_invalid_type_rejected(supplied):
    assert normalize_and_validate(build(type=supplied)) == (
        None,
        "error.invalid_transaction_type",
    )


# --- input shape and error precedence ---------------------------------------


def test_missing_keys_are_treated_as_empty():
    assert normalize_and_validate({}) == (None, "error.invalid_category")


def test_none_values_tolerated():
    # csv.DictReader yields None for columns a short row never reached.
    row = build(source=None)
    assert normalize_and_validate(row) == (None, "error.source_required")


def test_first_failure_wins_in_a_fixed_order():
    # Every field is invalid here; the category check runs first, and that
    # ordering is what the existing route behavior depends on.
    both_bad = {"date": "nope", "source": "", "amount": "x", "type": "x", "category": "x"}
    assert normalize_and_validate(both_bad) == (None, "error.invalid_category")

    date_and_source_bad = build(date="nope", source="")
    assert normalize_and_validate(date_and_source_bad) == (None, "error.invalid_date_format")


def test_input_mapping_is_not_mutated():
    row = build()
    normalize_and_validate(row)
    assert row == VALID


# --- the form adapter --------------------------------------------------------


def test_form_adapter_delegates_to_the_shared_rules():
    # The Add/Edit routes still call validate_transaction_form; it must be a
    # pass-through to the shared rules, not a second copy of them.
    from werkzeug.datastructures import MultiDict

    from blueprints.transactions import validate_transaction_form

    form = MultiDict(build(category="groceries", type="EXPENSE"))
    data, error = validate_transaction_form(form)

    assert error is None
    assert data == normalize_and_validate(build(category="groceries", type="EXPENSE"))[0]
    assert data["category"] == "Groceries"
    assert data["type"] == "expense"


def test_form_adapter_tolerates_a_form_missing_every_field():
    from werkzeug.datastructures import MultiDict

    from blueprints.transactions import validate_transaction_form

    assert validate_transaction_form(MultiDict()) == (None, "error.invalid_category")
