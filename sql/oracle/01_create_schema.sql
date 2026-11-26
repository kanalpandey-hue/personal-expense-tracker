-- =====================================================================
-- 01_create_schema.sql
-- Personal Expense Tracker - Oracle schema (Oracle 19c or later)
--
-- Creates:
--   Sequences : txn_seq, alert_seq
--   Tables    : categories, transactions, budgets, budget_alerts
--   Trigger   : trg_transactions_derive (fills derived columns)
--   Indexes   : on month / category / date columns
--
-- Run this script FIRST. It is safe to run again: existing objects
-- are dropped at the start.
--
-- Converted from sql/schema.sql (SQLite). Main changes:
--   TEXT  -> VARCHAR2(n)        REAL -> NUMBER(12,2)
--   date stored as text -> real DATE column
--   budgets.month '2024-01' (text) -> budget_month DATE '2024-01-01'
--   "DROP TABLE IF EXISTS" (not available before Oracle 23ai)
--      -> PL/SQL block that ignores "object does not exist" errors
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. Drop old objects (so the script can be re-run)
--    CASCADE CONSTRAINTS also removes foreign keys pointing at a table.
-- ---------------------------------------------------------------------
BEGIN
    FOR obj IN (SELECT object_name, object_type
                FROM   user_objects
                WHERE  object_type IN ('TABLE', 'SEQUENCE')
                AND    object_name IN ('BUDGET_ALERTS', 'TRANSACTIONS', 'BUDGETS',
                                       'CATEGORIES', 'TXN_SEQ', 'ALERT_SEQ'))
    LOOP
        IF obj.object_type = 'TABLE' THEN
            EXECUTE IMMEDIATE 'DROP TABLE ' || obj.object_name || ' CASCADE CONSTRAINTS PURGE';
        ELSE
            EXECUTE IMMEDIATE 'DROP SEQUENCE ' || obj.object_name;
        END IF;
    END LOOP;
END;
/


-- ---------------------------------------------------------------------
-- 1. Sequences
-- ---------------------------------------------------------------------
-- New transactions added through PL/SQL get IDs like TXN100001.
-- The loaded dataset uses TXN000001 - TXN001278, so starting at 100001
-- can never collide with existing IDs.
CREATE SEQUENCE txn_seq   START WITH 100001 INCREMENT BY 1 NOCACHE;

-- Primary-key generator for the budget_alerts log table.
CREATE SEQUENCE alert_seq START WITH 1      INCREMENT BY 1 NOCACHE;


-- ---------------------------------------------------------------------
-- 2. categories  (master / lookup table)
-- ---------------------------------------------------------------------
CREATE TABLE categories (
    category_name   VARCHAR2(30)  CONSTRAINT pk_categories PRIMARY KEY,
    category_group  VARCHAR2(15)  NOT NULL
                    CONSTRAINT chk_cat_group  CHECK (category_group IN ('Income', 'Essential', 'Discretionary')),
    cost_nature     VARCHAR2(10)  NOT NULL
                    CONSTRAINT chk_cat_nature CHECK (cost_nature IN ('Income', 'Fixed', 'Variable'))
);


-- ---------------------------------------------------------------------
-- 3. transactions  (every cleaned bank transaction)
-- ---------------------------------------------------------------------
CREATE TABLE transactions (
    transaction_id  VARCHAR2(12)   CONSTRAINT pk_transactions PRIMARY KEY,
    txn_date        DATE           NOT NULL,
    year_month      VARCHAR2(7)    NOT NULL,      -- 'YYYY-MM', filled by trigger
    description     VARCHAR2(100),
    category        VARCHAR2(30)   NOT NULL,
    amount          NUMBER(12,2)   NOT NULL,
    txn_type        VARCHAR2(6)    NOT NULL,
    payment_mode    VARCHAR2(15)   DEFAULT 'Unknown' NOT NULL,
    merchant        VARCHAR2(60),
    day_of_week     VARCHAR2(9)    NOT NULL,      -- 'Monday'..'Sunday', filled by trigger
    is_weekend      NUMBER(1)      DEFAULT 0 NOT NULL,   -- 1 = Sat/Sun, filled by trigger

    CONSTRAINT fk_txn_category  FOREIGN KEY (category) REFERENCES categories (category_name),
    CONSTRAINT chk_txn_amount   CHECK (amount >= 0),
    CONSTRAINT chk_txn_type     CHECK (txn_type IN ('Debit', 'Credit')),
    CONSTRAINT chk_txn_payment  CHECK (payment_mode IN ('UPI', 'Debit Card', 'Credit Card',
                                                        'Net Banking', 'Cash', 'Unknown')),
    CONSTRAINT chk_txn_weekend  CHECK (is_weekend IN (0, 1)),
    CONSTRAINT chk_txn_yrmonth  CHECK (REGEXP_LIKE(year_month, '^[0-9]{4}-(0[1-9]|1[0-2])$'))
);


-- ---------------------------------------------------------------------
-- 4. budgets  (planned budget per month per category)
--    budget_month is always the FIRST day of the month, e.g. 01-JAN-2024.
-- ---------------------------------------------------------------------
CREATE TABLE budgets (
    budget_month    DATE          NOT NULL,
    category        VARCHAR2(30)  NOT NULL,
    budget_amount   NUMBER(12,2)  NOT NULL,

    CONSTRAINT pk_budgets          PRIMARY KEY (budget_month, category),
    CONSTRAINT fk_budget_category  FOREIGN KEY (category) REFERENCES categories (category_name),
    CONSTRAINT chk_budget_amount   CHECK (budget_amount > 0),
    CONSTRAINT chk_budget_month    CHECK (budget_month = TRUNC(budget_month, 'MM'))
);


-- ---------------------------------------------------------------------
-- 5. budget_alerts  (log written by the PL/SQL package in 04_budget_plsql.sql)
--    DEFAULT alert_seq.NEXTVAL is supported from Oracle 12c onwards.
-- ---------------------------------------------------------------------
CREATE TABLE budget_alerts (
    alert_id         NUMBER        DEFAULT alert_seq.NEXTVAL CONSTRAINT pk_budget_alerts PRIMARY KEY,
    budget_month     DATE          NOT NULL,
    category         VARCHAR2(30)  NOT NULL,
    budget_amount    NUMBER(12,2)  NOT NULL,
    actual_spent     NUMBER(12,2)  NOT NULL,
    utilisation_pct  NUMBER(7,1)   NOT NULL,
    status           VARCHAR2(15)  NOT NULL,
    created_at       TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT fk_alert_budget  FOREIGN KEY (budget_month, category)
                                REFERENCES budgets (budget_month, category),
    CONSTRAINT chk_alert_status CHECK (status IN ('Near Limit', 'Over Budget'))
);


-- ---------------------------------------------------------------------
-- 6. Trigger: derive year_month, day_of_week and is_weekend from txn_date
--    so these columns can never disagree with the real date.
--    Also gives a new transaction an ID from txn_seq if none was supplied.
--    NLS_DATE_LANGUAGE=ENGLISH makes day names English on any server.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TRIGGER trg_transactions_derive
BEFORE INSERT OR UPDATE OF txn_date ON transactions
FOR EACH ROW
BEGIN
    IF INSERTING AND :NEW.transaction_id IS NULL THEN
        :NEW.transaction_id := 'TXN' || LPAD(txn_seq.NEXTVAL, 6, '0');
    END IF;

    :NEW.year_month  := TO_CHAR(:NEW.txn_date, 'YYYY-MM');
    :NEW.day_of_week := TO_CHAR(:NEW.txn_date, 'fmDay', 'NLS_DATE_LANGUAGE=ENGLISH');

    IF TO_CHAR(:NEW.txn_date, 'DY', 'NLS_DATE_LANGUAGE=ENGLISH') IN ('SAT', 'SUN') THEN
        :NEW.is_weekend := 1;
    ELSE
        :NEW.is_weekend := 0;
    END IF;
END;
/


-- ---------------------------------------------------------------------
-- 7. Indexes (Oracle indexes primary keys automatically, not foreign keys)
-- ---------------------------------------------------------------------
CREATE INDEX idx_txn_year_month ON transactions (year_month);
CREATE INDEX idx_txn_category   ON transactions (category);
CREATE INDEX idx_txn_date       ON transactions (txn_date);
CREATE INDEX idx_budget_cat     ON budgets (category);
CREATE INDEX idx_alert_budget   ON budget_alerts (budget_month, category);


-- ---------------------------------------------------------------------
-- 8. Quick check: should list 4 tables, 2 sequences, 1 trigger (all VALID)
-- ---------------------------------------------------------------------
SELECT object_type, object_name, status
FROM   user_objects
WHERE  object_name IN ('CATEGORIES', 'TRANSACTIONS', 'BUDGETS', 'BUDGET_ALERTS',
                       'TXN_SEQ', 'ALERT_SEQ', 'TRG_TRANSACTIONS_DERIVE')
ORDER  BY object_type, object_name;
