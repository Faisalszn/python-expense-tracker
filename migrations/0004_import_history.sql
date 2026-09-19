-- Records what each CSV import did, so "where did these 27 transactions come
-- from?" and "why were those 3 rows skipped?" stay answerable afterwards.
--
-- Deliberately absent: any stored duplicate fingerprint. Duplicate detection
-- is advisory and derived, computed fresh per import from the rows themselves,
-- so there is nothing here to migrate, backfill, or keep in step with edits.

CREATE TABLE IF NOT EXISTS import_batches (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    -- SHA-256 of the uploaded bytes. Non-unique on purpose: re-uploading the
    -- same file is worth warning about, not refusing — a user who deleted
    -- those transactions may well want them back.
    file_hash       TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    total_rows      INTEGER NOT NULL CHECK (total_rows >= 0),
    successful_rows INTEGER NOT NULL CHECK (successful_rows >= 0),
    failed_rows     INTEGER NOT NULL CHECK (failed_rows >= 0),
    duplicate_rows  INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_rows >= 0),
    -- completed: every row imported. partial: some rows failed validation.
    -- failed: the batch rolled back and nothing was imported.
    status          TEXT NOT NULL CHECK (status IN ('completed', 'partial', 'failed')),
    -- A row is imported, or fails validation, or is neither (a skipped
    -- duplicate) — so these can never add up to more than the file held.
    CHECK (successful_rows + failed_rows <= total_rows)
);

CREATE INDEX IF NOT EXISTS import_batches_user_created_idx
    ON import_batches (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS import_batches_user_hash_idx
    ON import_batches (user_id, file_hash);

CREATE TABLE IF NOT EXISTS import_row_errors (
    id         SERIAL PRIMARY KEY,
    import_id  INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    -- The line the row occupied in the file, matching what a spreadsheet shows.
    row_number INTEGER NOT NULL,
    -- A translation key, not a rendered sentence, so an error recorded in one
    -- language still reads correctly after the user switches to the other.
    error_key  TEXT NOT NULL,
    -- The offending line, truncated by the application before it gets here.
    raw_row    TEXT
);

CREATE INDEX IF NOT EXISTS import_row_errors_import_idx
    ON import_row_errors (import_id);

-- Where a transaction came from. Provenance, not derived data: it records a
-- fact that cannot drift or need recomputing when the row is later edited.
--
-- SET NULL rather than CASCADE: deleting import history must never delete a
-- user's money. The transactions survive, having simply lost their receipt.
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS import_id INTEGER
    REFERENCES import_batches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS transactions_import_idx ON transactions (import_id);
