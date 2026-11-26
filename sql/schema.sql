-- =====================================================================
-- schema.sql : Database design for the Personal Expense Tracker
-- Database engine: SQLite (file-based, no server needed)
-- =====================================================================

-- Master table of categories (one row per category)
DROP TABLE IF EXISTS categories;
CREATE TABLE categories (
    category_name   TEXT PRIMARY KEY,
    category_group  TEXT NOT NULL CHECK (category_group IN ('Income', 'Essential', 'Discretionary')),
    cost_nature     TEXT NOT NULL CHECK (cost_nature IN ('Income', 'Fixed', 'Variable'))
);

-- Every cleaned bank transaction
DROP TABLE IF EXISTS transactions;
CREATE TABLE transactions (
    transaction_id  TEXT PRIMARY KEY,
    txn_date        DATE NOT NULL,
    year_month      TEXT NOT NULL,          -- e.g. '2025-03'
    description     TEXT,
    category        TEXT NOT NULL REFERENCES categories(category_name),
    amount          REAL NOT NULL CHECK (amount >= 0),
    txn_type        TEXT NOT NULL CHECK (txn_type IN ('Debit', 'Credit')),
    payment_mode    TEXT,
    merchant        TEXT,
    day_of_week     TEXT,
    is_weekend      INTEGER                 -- 1 = Saturday/Sunday, 0 = weekday
);

-- Planned budget per month per category
DROP TABLE IF EXISTS budgets;
CREATE TABLE budgets (
    month           TEXT NOT NULL,
    category        TEXT NOT NULL REFERENCES categories(category_name),
    budget_amount   REAL NOT NULL CHECK (budget_amount > 0),
    PRIMARY KEY (month, category)
);

-- Indexes make the GROUP BY / WHERE queries faster
CREATE INDEX idx_txn_month    ON transactions(year_month);
CREATE INDEX idx_txn_category ON transactions(category);
