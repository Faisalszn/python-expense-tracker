"""Parse an uploaded CSV into a preview, without touching the database.

The whole module is pure: bytes in, a description of what *would* happen out.
Nothing here writes, and the confirm step re-runs it rather than trusting
anything the preview handed to the browser.

Row validation is delegated to `transaction_rules`, the same code the Add and
Edit forms use, so a row rejected here would have been rejected there and for
the same stated reason.
"""

import csv
import io
from dataclasses import dataclass, field

from services.transaction_rules import (
    TRANSACTION_FIELDS,
    canonical_key,
    normalize_and_validate,
    parse_date,
)

# A bound on how much work one upload can ask for. The byte limit
# (MAX_CONTENT_LENGTH) stops an enormous file; this stops a merely large one
# from producing a preview page nobody can read.
MAX_IMPORT_ROWS = 2000

VALID = "valid"
INVALID = "invalid"
DUPLICATE = "duplicate"


@dataclass(frozen=True)
class PreviewRow:
    """One data row, as the preview table renders it."""

    number: int
    values: dict
    status: str
    normalized: dict = None
    error_key: str = None

    @property
    def is_valid(self):
        return self.status == VALID


@dataclass(frozen=True)
class ImportPreview:
    """What an upload would do, if confirmed."""

    rows: list = field(default_factory=list)
    file_error_key: str = None
    file_error_detail: str = None

    @property
    def valid_count(self):
        return sum(1 for row in self.rows if row.status == VALID)

    @property
    def invalid_count(self):
        return sum(1 for row in self.rows if row.status == INVALID)

    @property
    def duplicate_count(self):
        return sum(1 for row in self.rows if row.status == DUPLICATE)

    @property
    def total_count(self):
        return len(self.rows)

    @property
    def importable_rows(self):
        """The rows a confirmation would insert, duplicates excluded."""
        return [row for row in self.rows if row.status == VALID]


def _decode(raw_bytes):
    """Decode an upload as UTF-8, tolerating the BOM Excel writes."""
    return raw_bytes.decode("utf-8-sig")


def _normalize_headers(fieldnames):
    """Trim and case-fold the header row.

    A column called "Date" or " amount" is the same column; anything more
    forgiving than that would be column mapping, which V13 does not do.
    """
    return [(name or "").strip().lower() for name in fieldnames]


def parse(raw_bytes):
    """Parse and validate an upload, without checking for duplicates.

    Duplicate detection needs to know which dates the file covers, so it runs
    as a second step once the rows are known.
    """
    try:
        text = _decode(raw_bytes)
    except UnicodeDecodeError:
        return ImportPreview(file_error_key="error.csv_not_utf8")

    if not text.strip():
        return ImportPreview(file_error_key="error.csv_empty")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return ImportPreview(file_error_key="error.csv_empty")

    headers = _normalize_headers(reader.fieldnames)
    missing = [name for name in TRANSACTION_FIELDS if name not in headers]
    if missing:
        return ImportPreview(
            file_error_key="error.csv_missing_headers",
            file_error_detail=", ".join(missing),
        )

    # Columns beyond the canonical five are ignored rather than rejected:
    # they cost nothing, and refusing a file over an extra note column would
    # be needlessly strict.
    reader.fieldnames = headers

    rows = []
    for row in reader:
        if len(rows) >= MAX_IMPORT_ROWS:
            return ImportPreview(
                file_error_key="error.csv_too_many_rows",
                file_error_detail=str(MAX_IMPORT_ROWS),
            )

        values = {name: (row.get(name) or "") for name in TRANSACTION_FIELDS}
        normalized, error_key = normalize_and_validate(row)

        rows.append(
            PreviewRow(
                # The line the row occupies in the file, so it matches what a
                # spreadsheet shows when the user goes to fix it.
                number=reader.line_num,
                values=values,
                status=INVALID if error_key else VALID,
                normalized=normalized,
                error_key=error_key,
            )
        )

    if not rows:
        return ImportPreview(file_error_key="error.csv_empty")

    return ImportPreview(rows=rows)


def dates_covered(preview):
    """The distinct dates the valid rows fall on.

    Narrows the duplicate lookup to the days the file actually touches,
    instead of reading the account's whole history.
    """
    return sorted({parse_date(row.normalized["date"]) for row in preview.rows if row.is_valid})


def mark_duplicates(preview, user_id, existing_keys):
    """Flag rows already recorded, or repeated earlier in the same file.

    Advisory only. A genuine pair of identical transactions — two coffees at
    the same shop on the same day — is a real thing to record, so this marks
    the later one and leaves importing it to an explicit choice rather than
    refusing it outright.
    """
    seen = set(existing_keys)
    rows = []

    for row in preview.rows:
        if not row.is_valid:
            rows.append(row)
            continue

        key = canonical_key(user_id, row.normalized)
        if key in seen:
            rows.append(
                PreviewRow(
                    number=row.number,
                    values=row.values,
                    status=DUPLICATE,
                    normalized=row.normalized,
                    error_key="error.duplicate_row",
                )
            )
        else:
            seen.add(key)
            rows.append(row)

    return ImportPreview(rows=rows)


def build_preview(raw_bytes, user_id, existing_keys_for_dates):
    """Parse an upload and describe what importing it would do.

    `existing_keys_for_dates` is injected rather than queried here so this
    module stays free of the database: the route supplies a callable that maps
    a list of dates to the canonical keys already stored on them.
    """
    preview = parse(raw_bytes)
    if preview.file_error_key:
        return preview

    dates = dates_covered(preview)
    return mark_duplicates(preview, user_id, existing_keys_for_dates(dates))
