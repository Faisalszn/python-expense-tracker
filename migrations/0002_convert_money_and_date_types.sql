-- Converts transactions.amount / budgets.monthly_limit from REAL to
-- NUMERIC(12, 2), and transactions.date from TEXT to DATE, for any database
-- created before those types were fixed. Guarded so it's a no-op against a
-- database created fresh by 0001 (which already uses the correct types).

DO $$
BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'amount') != 'numeric'
    THEN
        ALTER TABLE transactions
            ALTER COLUMN amount TYPE NUMERIC(12, 2) USING amount::numeric(12, 2);
    END IF;

    IF (SELECT data_type FROM information_schema.columns
        WHERE table_name = 'budgets' AND column_name = 'monthly_limit') != 'numeric'
    THEN
        ALTER TABLE budgets
            ALTER COLUMN monthly_limit TYPE NUMERIC(12, 2) USING monthly_limit::numeric(12, 2);
    END IF;

    IF (SELECT data_type FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'date') != 'date'
    THEN
        ALTER TABLE transactions
            ALTER COLUMN date TYPE DATE USING date::date;
    END IF;
END $$;
