-- =====================================================================
-- 06_create_views.sql
-- Two simple views for the Personal Expense Tracker (Oracle 19c or later)
--
--   v_monthly_summary : income, expense, savings and savings rate per month
--   v_budget_status   : budget, actual spending, remaining budget and
--                       status for every month + category
--
-- Requires: 01_create_schema.sql (tables). Run after 02 and 03 so the
-- check queries at the bottom return data. Does NOT need 04 or 05.
--
-- What is a view?
--   A view is a SAVED QUERY with a name. It stores no data of its own -
--   every time you select from it, Oracle runs the query on the current
--   tables. So a new transaction is reflected in the views immediately.
--
-- CREATE OR REPLACE means the script can be run again safely.
-- Views have no ORDER BY - sort when you SELECT from them.
-- =====================================================================


-- ---------------------------------------------------------------------
-- View 1: monthly cash flow
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_monthly_summary AS
SELECT
    year_month,
    ROUND(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE 0 END), 2)       AS total_income,
    ROUND(SUM(CASE WHEN txn_type = 'Debit'  THEN amount ELSE 0 END), 2)       AS total_expense,
    ROUND(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE -amount END), 2) AS net_savings,
    ROUND(100 * SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE -amount END)
              / NULLIF(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE 0 END), 0), 1)
                                                                              AS savings_rate_pct
FROM   transactions
GROUP  BY year_month;


-- ---------------------------------------------------------------------
-- View 2: budget vs actual with status
--   remaining_budget > 0  -> money left,   < 0 -> overspent
--   Status rules are the same as the Python project and PKG_BUDGET:
--   > 100% Over Budget, >= 80% Near Limit, otherwise Within Budget
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_budget_status AS
SELECT
    TO_CHAR(b.budget_month, 'YYYY-MM')                          AS year_month,
    b.category,
    b.budget_amount,
    ROUND(NVL(SUM(t.amount), 0), 2)                             AS actual_spent,
    ROUND(b.budget_amount - NVL(SUM(t.amount), 0), 2)           AS remaining_budget,
    ROUND(100 * NVL(SUM(t.amount), 0) / b.budget_amount, 1)     AS utilisation_pct,
    CASE
        WHEN NVL(SUM(t.amount), 0) >  b.budget_amount       THEN 'Over Budget'
        WHEN NVL(SUM(t.amount), 0) >= 0.8 * b.budget_amount THEN 'Near Limit'
        ELSE 'Within Budget'
    END                                                         AS status
FROM   budgets b
LEFT JOIN transactions t
       ON  t.category = b.category
       AND t.txn_type = 'Debit'
       AND t.txn_date >= b.budget_month
       AND t.txn_date <  ADD_MONTHS(b.budget_month, 1)
GROUP  BY b.budget_month, b.category, b.budget_amount;


-- ---------------------------------------------------------------------
-- Check 1: both views were created. EXPECTED: 2 rows, both VALID.
-- ---------------------------------------------------------------------
SELECT object_name, status
FROM   user_objects
WHERE  object_type = 'VIEW'
AND    object_name IN ('V_MONTHLY_SUMMARY', 'V_BUDGET_STATUS')
ORDER  BY object_name;


-- ---------------------------------------------------------------------
-- Check 2: monthly summary
-- EXPECTED: 24 rows. First rows:
--   YEAR_MONTH  TOTAL_INCOME  TOTAL_EXPENSE  NET_SAVINGS  SAVINGS_RATE_PCT
--   2024-01         68000       51866.04      16133.96        23.7
--   2024-02      87594.28       41825.07      45769.21        52.3
--   2024-03      74266.27       73633.82        632.45         0.9
-- ---------------------------------------------------------------------
SELECT *
FROM   v_monthly_summary
ORDER  BY year_month;


-- EXPECTED: 2 deficit months -> 2024-07 (-4171.41) and 2025-03 (-5414.23)
SELECT year_month, net_savings
FROM   v_monthly_summary
WHERE  net_savings < 0
ORDER  BY year_month;


-- EXPECTED: total_income 1883674.03, total_expense 1460802.19,
--           net_savings 422871.84  (same as the Python analysis)
SELECT SUM(total_income)  AS total_income,
       SUM(total_expense) AS total_expense,
       SUM(net_savings)   AS net_savings
FROM   v_monthly_summary;


-- ---------------------------------------------------------------------
-- Check 3: budget status
-- EXPECTED: 3 rows ->  Near Limit 101,  Over Budget 94,  Within Budget 93
--           (288 rows in total = 12 categories x 24 months)
-- ---------------------------------------------------------------------
SELECT status, COUNT(*) AS num_rows
FROM   v_budget_status
GROUP  BY status
ORDER  BY status;


-- EXPECTED (October 2025, first 3 rows):
--   CATEGORY       BUDGET_AMOUNT  ACTUAL_SPENT  REMAINING_BUDGET  UTILISATION_PCT  STATUS
--   Shopping               7000      14986.57          -7986.57            214.1  Over Budget
--   Travel                 5000       8147.64          -3147.64              163  Over Budget
--   Food and Dining        6000       8843.39          -2843.39            147.4  Over Budget
--   (comments write "and" instead of the ampersand symbol, because SQL*Plus and
--    SQL Developer treat that symbol as a variable prompt, even inside comments)
SELECT category, budget_amount, actual_spent, remaining_budget, utilisation_pct, status
FROM   v_budget_status
WHERE  year_month = '2025-10'
ORDER  BY utilisation_pct DESC;


-- EXPECTED: total_budget 1502800, total_actual 1460802.19, total_remaining 41997.81
SELECT SUM(budget_amount)    AS total_budget,
       SUM(actual_spent)     AS total_actual,
       SUM(remaining_budget) AS total_remaining
FROM   v_budget_status;
