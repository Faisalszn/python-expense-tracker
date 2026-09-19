"""Render stored transactions as Mizan's canonical CSV.

The column set is `transaction_rules.TRANSACTION_FIELDS`, the same tuple the
validator reads, so export and import cannot drift apart into two slightly
different ideas of what a Mizan CSV looks like.

Pure: takes rows, yields text. No Flask, no database — which is what makes the
exact bytes a user downloads testable without either.
"""

import csv
import io

from services.transaction_rules import TRANSACTION_FIELDS

# Excel assumes the host encoding for a .csv unless the file opens with a byte
# order mark, which mangles any non-ASCII source name — Arabic ones especially.
# Python reads it back transparently with the "utf-8-sig" codec.
BYTE_ORDER_MARK = "﻿"


def to_row(transaction):
    """Map one get_transactions() row to the canonical columns.

    Drops the database id deliberately: it is an internal identifier that means
    nothing outside this installation, and re-importing a file that carried one
    would either be ignored or, worse, be trusted.
    """
    _, date, source, amount, transaction_type, category = transaction

    return (
        date.isoformat(),
        source,
        f"{amount:.2f}",
        transaction_type,
        category,
    )


def export_csv(transactions):
    """Yield the canonical CSV one row at a time.

    A generator so a long history is never assembled into one large string in
    memory before the response starts.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def drain():
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return text

    writer.writerow(TRANSACTION_FIELDS)
    yield BYTE_ORDER_MARK + drain()

    for transaction in transactions:
        writer.writerow(to_row(transaction))
        yield drain()
