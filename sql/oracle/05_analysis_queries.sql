-- =====================================================================
-- 05_analysis_queries.sql
-- The 10 business questions from sql/analysis_queries.sql, rewritten
-- for Oracle 19c or later. Same logic and same results as the SQLite /
-- pandas versions.
--
-- Requires: 01, 02 and 03 have been run.
--
-- Oracle-specific changes vs. the SQLite version:
--   * LIMIT 10                    -> FETCH FIRST 10 ROWS ONLY   (Q6)
--   * GROUP BY <column alias>     -> GROUP BY <full expression> (Q7, Q9, Q10)
--     (grouping by an alias is only allowed from Oracle 23ai)
--   * SUBSTR(year_month, 1, 4)    -> EXTRACT(YEAR FROM txn_date) (Q9, Q10)
--   * budgets joined by DATE RANGE instead of text month   (Q3, Q4)
--       txn_date >= budget_month AND txn_date < ADD_MONTHS(budget_month, 1)
--     (lets Oracle use the index on txn_date)
--   * NULLIF(x, 0) guards every division against divide-by-zero
--
-- EXPECTED results above each query come from the verified project
-- outputs in reports/sql_outputs/. Oracle hides trailing zeros, so it
-- shows 68000 instead of 68000.00 - the values are the same.
-- Comments write "Food and Dining" without the ampersand symbol, because
-- SQL*Plus / SQL Developer treat that symbol as a variable prompt.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1. How much came in, went out, and was saved each month?
--
-- EXPECTED: 24 rows (2024-01 to 2025-12). First and last rows:
--  YEAR_MONTH  TOTAL_INCOME  TOTAL_EXPENSE  NET_SAVINGS
--  2024-01            68000       51866.04     16133.96
--  2024-02         87594.28       41825.07     45769.21
--  2024-03         74266.27       73633.82       632.45
--  2025-12          86338.1       68398.24     17939.86
-- ---------------------------------------------------------------------
SELECT
    year_month,
    ROUND(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE 0 END), 2)       AS total_income,
    ROUND(SUM(CASE WHEN txn_type = 'Debit'  THEN amount ELSE 0 END), 2)       AS total_expense,
    ROUND(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE -amount END), 2) AS net_savings
FROM   transactions
GROUP  BY year_month
ORDER  BY year_month;


-- ---------------------------------------------------------------------
-- Q2. Which categories take the most money, and what share of the total?
--
-- EXPECTED: 12 rows. First rows and last row:
--  CATEGORY       NUM_TRANSACTIONS  TOTAL_SPENT  AVG_TRANSACTION  SHARE_PCT
--  Rent                         24       369000            15375      25.26
--  Shopping                     85    191944.01          2258.16      13.14
--  Groceries                   184     162982.7           885.78      11.16
--  Subscriptions                96        33984              354       2.33
-- ---------------------------------------------------------------------
SELECT
    category,
    COUNT(*)                AS num_transactions,
    ROUND(SUM(amount), 2)   AS total_spent,
    ROUND(AVG(amount), 2)   AS avg_transaction,
    ROUND(100 * SUM(amount) /
          NULLIF((SELECT SUM(amount) FROM transactions WHERE txn_type = 'Debit'), 0), 2) AS share_pct
FROM   transactions
WHERE  txn_type = 'Debit'
GROUP  BY category
ORDER  BY total_spent DESC;


-- ---------------------------------------------------------------------
-- Q3. For every month and category, was the budget respected?
--     LEFT JOIN keeps budget rows even when nothing was spent.
--     Status thresholds match the Python code: > 100% Over Budget,
--     >= 80% Near Limit, otherwise Within Budget.
--
-- EXPECTED: 288 rows (12 categories x 24 months). First rows:
--  BUDGET_MONTH  CATEGORY        BUDGET_AMOUNT  ACTUAL_SPENT  VARIANCE  UTILISATION_PCT  STATUS
--  2024-01       Education                1500       6342.48  -4842.48            422.8  Over Budget
--  2024-01       Shopping                 6000       7950.71  -1950.71            132.5  Over Budget
--  2024-01       Transportation           6000       6326.91   -326.91            105.4  Over Budget
--  Status totals: Near Limit 101, Over Budget 94, Within Budget 93.
--  Rows with equal UTILISATION_PCT (e.g. Rent and Insurance at 100) may swap places.
-- ---------------------------------------------------------------------
SELECT
    TO_CHAR(b.budget_month, 'YYYY-MM')                                   AS budget_month,
    b.category,
    b.budget_amount,
    ROUND(NVL(SUM(t.amount), 0), 2)                                      AS actual_spent,
    ROUND(b.budget_amount - NVL(SUM(t.amount), 0), 2)                    AS variance,
    ROUND(100 * NVL(SUM(t.amount), 0) / b.budget_amount, 1)              AS utilisation_pct,
    CASE
        WHEN NVL(SUM(t.amount), 0) >  b.budget_amount       THEN 'Over Budget'
        WHEN NVL(SUM(t.amount), 0) >= 0.8 * b.budget_amount THEN 'Near Limit'
        ELSE 'Within Budget'
    END                                                                  AS status
FROM   budgets b
LEFT JOIN transactions t
       ON  t.category = b.category
       AND t.txn_type = 'Debit'
       AND t.txn_date >= b.budget_month
       AND t.txn_date <  ADD_MONTHS(b.budget_month, 1)
GROUP  BY b.budget_month, b.category, b.budget_amount
ORDER  BY b.budget_month, utilisation_pct DESC;


-- ---------------------------------------------------------------------
-- Q4. How often did each category go over budget? (CTE with WITH)
--
-- EXPECTED: 12 rows. First rows and last row:
--  CATEGORY         MONTHS_OVER_BUDGET  MONTHS_TRACKED  TOTAL_OVERSPEND
--  Shopping                         16              24         65559.01
--  Entertainment                    13              24         16165.97
--  Food and Dining                  12              24         31505.34
--  Subscriptions                     0              24                0
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT b.budget_month,
           b.category,
           b.budget_amount,
           NVL(SUM(t.amount), 0) AS actual
    FROM   budgets b
    LEFT JOIN transactions t
           ON  t.category = b.category
           AND t.txn_type = 'Debit'
           AND t.txn_date >= b.budget_month
           AND t.txn_date <  ADD_MONTHS(b.budget_month, 1)
    GROUP  BY b.budget_month, b.category, b.budget_amount
)
SELECT
    category,
    SUM(CASE WHEN actual > budget_amount THEN 1 ELSE 0 END)                           AS months_over_budget,
    COUNT(*)                                                                          AS months_tracked,
    ROUND(SUM(CASE WHEN actual > budget_amount THEN actual - budget_amount ELSE 0 END), 2) AS total_overspend
FROM   monthly
GROUP  BY category
ORDER  BY months_over_budget DESC, total_overspend DESC;


-- ---------------------------------------------------------------------
-- Q5. How does the user pay? (digital vs cash behaviour)
--
-- EXPECTED: 6 rows:
--  PAYMENT_MODE  NUM_TRANSACTIONS  TOTAL_SPENT  TXN_SHARE_PCT
--  UPI                        672     602763.8          55.04
--  Net Banking                 79    441855.58           6.47
--  Credit Card                228    221081.12          18.67
--  Debit Card                 124    116148.26          10.16
--  Cash                        83     54132.01            6.8
--  Unknown                     35     24821.42           2.87
-- ---------------------------------------------------------------------
SELECT
    payment_mode,
    COUNT(*)               AS num_transactions,
    ROUND(SUM(amount), 2)  AS total_spent,
    ROUND(100 * COUNT(*) /
          NULLIF((SELECT COUNT(*) FROM transactions WHERE txn_type = 'Debit'), 0), 2) AS txn_share_pct
FROM   transactions
WHERE  txn_type = 'Debit'
GROUP  BY payment_mode
ORDER  BY total_spent DESC;


-- ---------------------------------------------------------------------
-- Q6. Top 10 merchants by money spent
--     FETCH FIRST ... ROWS ONLY is Oracle's version of LIMIT (12c+).
--
-- EXPECTED: 10 rows. First rows and last row:
--  MERCHANT                CATEGORY        VISITS  TOTAL_SPENT
--  House Rent - Landlord   Rent                24       369000
--  Indian Oil Petrol Pump  Transportation      59     68603.87
--  Croma                   Shopping            14     68036.48
--  Star Health Insurance   Insurance            2        37000
-- ---------------------------------------------------------------------
SELECT merchant,
       category,
       COUNT(*)               AS visits,
       ROUND(SUM(amount), 2)  AS total_spent
FROM   transactions
WHERE  txn_type = 'Debit'
GROUP  BY merchant, category
ORDER  BY total_spent DESC
FETCH FIRST 10 ROWS ONLY;


-- ---------------------------------------------------------------------
-- Q7. Do we spend more on weekends? (variable spending only)
--     The CASE expression is repeated in GROUP BY because Oracle 19c
--     does not allow grouping by a column alias.
--
-- EXPECTED: 2 rows:
--  DAY_TYPE  NUM_TRANSACTIONS  TOTAL_SPENT  AVG_TRANSACTION
--  Weekday                693    623444.93           899.63
--  Weekend                286    258517.17           903.91
-- ---------------------------------------------------------------------
SELECT
    CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END  AS day_type,
    COUNT(*)                                                      AS num_transactions,
    ROUND(SUM(t.amount), 2)                                       AS total_spent,
    ROUND(AVG(t.amount), 2)                                       AS avg_transaction
FROM   transactions t
JOIN   categories c ON c.category_name = t.category
WHERE  t.txn_type = 'Debit'
AND    c.cost_nature = 'Variable'
GROUP  BY CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END
ORDER  BY day_type;


-- ---------------------------------------------------------------------
-- Q8. Month-over-month change in spending (window function LAG)
--
-- EXPECTED: 24 rows. First rows and last row (empty = NULL, there is no month before Jan 2024):
--  YEAR_MONTH  EXPENSE   PREVIOUS_MONTH  CHANGE_PCT
--  2024-01     51866.04
--  2024-02     41825.07        51866.04       -19.4
--  2024-03     73633.82        41825.07        76.1
--  2025-12     68398.24        64939.49         5.3
-- ---------------------------------------------------------------------
WITH monthly_expense AS (
    SELECT year_month, SUM(amount) AS expense
    FROM   transactions
    WHERE  txn_type = 'Debit'
    GROUP  BY year_month
)
SELECT
    year_month,
    ROUND(expense, 2)                                        AS expense,
    ROUND(LAG(expense) OVER (ORDER BY year_month), 2)        AS previous_month,
    ROUND(100 * (expense - LAG(expense) OVER (ORDER BY year_month))
          / NULLIF(LAG(expense) OVER (ORDER BY year_month), 0), 1) AS change_pct
FROM   monthly_expense
ORDER  BY year_month;


-- ---------------------------------------------------------------------
-- Q9. Top 5 categories inside each year (window function RANK)
--
-- EXPECTED: 10 rows (top 5 per year):
--  TXN_YEAR  CATEGORY         TOTAL_SPENT  RANK_IN_YEAR
--  2024      Rent                  180000             1
--  2024      Groceries           89917.84             2
--  2024      Shopping            88307.58             3
--  2024      Food and Dining     87338.32             4
--  2024      Transportation      61394.99             5
--  2025      Rent                  189000             1
--  2025      Shopping           103636.43             2
--  2025      Transportation      73208.49             3
--  2025      Groceries           73064.86             4
--  2025      Food and Dining     60583.89             5
-- ---------------------------------------------------------------------
SELECT txn_year, category, total_spent, rank_in_year
FROM (
    SELECT
        EXTRACT(YEAR FROM txn_date)                                              AS txn_year,
        category,
        ROUND(SUM(amount), 2)                                                    AS total_spent,
        RANK() OVER (PARTITION BY EXTRACT(YEAR FROM txn_date)
                     ORDER BY SUM(amount) DESC)                                  AS rank_in_year
    FROM   transactions
    WHERE  txn_type = 'Debit'
    GROUP  BY EXTRACT(YEAR FROM txn_date), category
)
WHERE  rank_in_year <= 5
ORDER  BY txn_year, rank_in_year;


-- ---------------------------------------------------------------------
-- Q10. Needs vs wants (vs income) per year - input for the 50/30/20 rule
--
-- EXPECTED: 6 rows:
--  TXN_YEAR  CATEGORY_GROUP  TOTAL
--  2024      Discretionary   244106.83
--  2024      Essential       457365.63
--  2024      Income          910382.86
--  2025      Discretionary   269961.01
--  2025      Essential       489368.72
--  2025      Income          973291.17
-- ---------------------------------------------------------------------
SELECT
    EXTRACT(YEAR FROM t.txn_date)  AS txn_year,
    c.category_group,
    ROUND(SUM(t.amount), 2)        AS total
FROM   transactions t
JOIN   categories c ON c.category_name = t.category
GROUP  BY EXTRACT(YEAR FROM t.txn_date), c.category_group
ORDER  BY txn_year, c.category_group;
