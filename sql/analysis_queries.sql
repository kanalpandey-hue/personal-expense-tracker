-- =====================================================================
-- analysis_queries.sql : Business questions answered with SQL
-- Each query starts with a line "-- name: <query_name>" so that
-- src/sql_analysis.py can find, run and save each one separately.
-- =====================================================================

-- name: q01_monthly_cash_flow
-- Q1. How much came in, went out, and was saved each month?
SELECT
    year_month,
    ROUND(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE 0 END), 2) AS total_income,
    ROUND(SUM(CASE WHEN txn_type = 'Debit'  THEN amount ELSE 0 END), 2) AS total_expense,
    ROUND(SUM(CASE WHEN txn_type = 'Credit' THEN amount ELSE -amount END), 2) AS net_savings
FROM transactions
GROUP BY year_month
ORDER BY year_month;

-- name: q02_category_spend
-- Q2. Which categories take the most money, and what share of the total?
SELECT
    category,
    COUNT(*)                     AS num_transactions,
    ROUND(SUM(amount), 2)        AS total_spent,
    ROUND(AVG(amount), 2)        AS avg_transaction,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM transactions WHERE txn_type = 'Debit'), 2) AS share_pct
FROM transactions
WHERE txn_type = 'Debit'
GROUP BY category
ORDER BY total_spent DESC;

-- name: q03_budget_vs_actual
-- Q3. For every month and category, was the budget respected?
--     LEFT JOIN keeps budget rows even when nothing was spent.
SELECT
    b.month,
    b.category,
    b.budget_amount,
    ROUND(COALESCE(SUM(t.amount), 0), 2)                            AS actual_spent,
    ROUND(b.budget_amount - COALESCE(SUM(t.amount), 0), 2)          AS variance,
    ROUND(100.0 * COALESCE(SUM(t.amount), 0) / b.budget_amount, 1)  AS utilisation_pct,
    CASE
        WHEN COALESCE(SUM(t.amount), 0) > b.budget_amount        THEN 'Over Budget'
        WHEN COALESCE(SUM(t.amount), 0) >= 0.8 * b.budget_amount THEN 'Near Limit'
        ELSE 'Within Budget'
    END AS status
FROM budgets b
LEFT JOIN transactions t
       ON t.year_month = b.month
      AND t.category   = b.category
      AND t.txn_type   = 'Debit'
GROUP BY b.month, b.category, b.budget_amount
ORDER BY b.month, utilisation_pct DESC;

-- name: q04_overspend_frequency
-- Q4. How often did each category go over budget? (uses a CTE)
WITH monthly AS (
    SELECT b.month, b.category, b.budget_amount,
           COALESCE(SUM(t.amount), 0) AS actual
    FROM budgets b
    LEFT JOIN transactions t
           ON t.year_month = b.month AND t.category = b.category AND t.txn_type = 'Debit'
    GROUP BY b.month, b.category, b.budget_amount
)
SELECT
    category,
    SUM(CASE WHEN actual > budget_amount THEN 1 ELSE 0 END)                        AS months_over_budget,
    COUNT(*)                                                                        AS months_tracked,
    ROUND(SUM(CASE WHEN actual > budget_amount THEN actual - budget_amount ELSE 0 END), 2) AS total_overspend
FROM monthly
GROUP BY category
ORDER BY months_over_budget DESC, total_overspend DESC;

-- name: q05_payment_mode_usage
-- Q5. How does the user pay? (digital vs cash behaviour)
SELECT
    payment_mode,
    COUNT(*)              AS num_transactions,
    ROUND(SUM(amount), 2) AS total_spent,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM transactions WHERE txn_type = 'Debit'), 2) AS txn_share_pct
FROM transactions
WHERE txn_type = 'Debit'
GROUP BY payment_mode
ORDER BY total_spent DESC;

-- name: q06_top_merchants
-- Q6. Top 10 merchants by money spent
SELECT merchant, category, COUNT(*) AS visits, ROUND(SUM(amount), 2) AS total_spent
FROM transactions
WHERE txn_type = 'Debit'
GROUP BY merchant, category
ORDER BY total_spent DESC
LIMIT 10;

-- name: q07_weekend_vs_weekday
-- Q7. Do we spend more on weekends? (variable spending only, joined to categories)
SELECT
    CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(*)                                                     AS num_transactions,
    ROUND(SUM(t.amount), 2)                                      AS total_spent,
    ROUND(AVG(t.amount), 2)                                      AS avg_transaction
FROM transactions t
JOIN categories c ON c.category_name = t.category
WHERE t.txn_type = 'Debit' AND c.cost_nature = 'Variable'
GROUP BY day_type;

-- name: q08_month_over_month_change
-- Q8. Month-over-month change in spending (window function LAG)
WITH monthly_expense AS (
    SELECT year_month, SUM(amount) AS expense
    FROM transactions
    WHERE txn_type = 'Debit'
    GROUP BY year_month
)
SELECT
    year_month,
    ROUND(expense, 2)                                          AS expense,
    ROUND(LAG(expense) OVER (ORDER BY year_month), 2)          AS previous_month,
    ROUND(100.0 * (expense - LAG(expense) OVER (ORDER BY year_month))
          / LAG(expense) OVER (ORDER BY year_month), 1)        AS change_pct
FROM monthly_expense
ORDER BY year_month;

-- name: q09_category_rank_per_year
-- Q9. Rank categories inside each year (window function RANK)
SELECT *
FROM (
    SELECT
        SUBSTR(year_month, 1, 4)                                              AS year,
        category,
        ROUND(SUM(amount), 2)                                                 AS total_spent,
        RANK() OVER (PARTITION BY SUBSTR(year_month, 1, 4) ORDER BY SUM(amount) DESC) AS rank_in_year
    FROM transactions
    WHERE txn_type = 'Debit'
    GROUP BY year, category
)
WHERE rank_in_year <= 5
ORDER BY year, rank_in_year;

-- name: q10_essential_vs_discretionary
-- Q10. Needs vs Wants split per year (50/30/20 rule input)
SELECT
    SUBSTR(t.year_month, 1, 4) AS year,
    c.category_group,
    ROUND(SUM(t.amount), 2)    AS total
FROM transactions t
JOIN categories c ON c.category_name = t.category
GROUP BY year, c.category_group
ORDER BY year, c.category_group;
