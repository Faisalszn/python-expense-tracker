-- Supports the month-scoped dashboard summary and budget progress, which look
-- transactions up by user and date range. Without this, scoping the dashboard
-- to the current month turns every page load into a sequential scan of the
-- user's whole history, which is the opposite of the point.

CREATE INDEX IF NOT EXISTS transactions_user_date_idx ON transactions (user_id, date);
