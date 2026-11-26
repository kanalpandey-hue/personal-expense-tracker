-- =====================================================================
-- 04_budget_plsql.sql
-- PL/SQL package PKG_BUDGET: budget validation and budget utilisation
-- (Oracle 19c or later)
--
-- Requires: 01, 02 and 03 have been run.
--
-- What it contains
--   Functions
--     get_budget_amount    - planned budget for a month + category
--     get_actual_spent     - money actually spent (debits) in that month
--     get_utilisation_pct  - actual / budget * 100
--     get_budget_status    - 'Within Budget' / 'Near Limit' / 'Over Budget'
--   Procedures
--     validate_budget      - checks a budget before it is saved
--     set_budget           - validate + insert or update (MERGE) a budget
--     check_budget         - computes utilisation and logs an alert
--     record_expense       - validate + insert an expense + check budget
--     print_monthly_report - budget vs actual report using a CURSOR
--
-- The thresholds are the same as the Python project (src/config.py):
--   > 100 %  -> Over Budget,   >= 80 %  -> Near Limit,   else Within Budget
--
-- Error codes raised (RAISE_APPLICATION_ERROR):
--   -20001 unknown category            -20005 invalid amount
--   -20002 income category used        -20006 invalid date
--   -20003 month missing               -20007 invalid payment mode
--   -20004 no budget for month         -20008 merchant missing
--
-- The procedures do NOT commit. The caller decides COMMIT or ROLLBACK,
-- which keeps a group of changes all-or-nothing.
--
-- SQL Developer / SQL*Plus users: run  SET SERVEROUTPUT ON  first to see
-- DBMS_OUTPUT messages. Oracle Live SQL shows them automatically.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Package specification (the public "menu" of the package)
-- ---------------------------------------------------------------------
CREATE OR REPLACE PACKAGE pkg_budget AS

    c_near_limit_pct   CONSTANT NUMBER := 80;
    c_over_budget_pct  CONSTANT NUMBER := 100;
    c_max_amount       CONSTANT NUMBER := 1000000;   -- Rs 10 lakh sanity limit

    FUNCTION get_budget_amount   (p_month IN DATE, p_category IN VARCHAR2) RETURN NUMBER;
    FUNCTION get_actual_spent    (p_month IN DATE, p_category IN VARCHAR2) RETURN NUMBER;
    FUNCTION get_utilisation_pct (p_month IN DATE, p_category IN VARCHAR2) RETURN NUMBER;
    FUNCTION get_budget_status   (p_utilisation_pct IN NUMBER) RETURN VARCHAR2;

    PROCEDURE validate_budget (p_month IN DATE, p_category IN VARCHAR2, p_amount IN NUMBER);
    PROCEDURE set_budget      (p_month IN DATE, p_category IN VARCHAR2, p_amount IN NUMBER);
    PROCEDURE check_budget    (p_month IN DATE, p_category IN VARCHAR2);

    PROCEDURE record_expense (
        p_txn_date      IN  DATE,
        p_category      IN  VARCHAR2,
        p_amount        IN  NUMBER,
        p_merchant      IN  VARCHAR2,
        p_payment_mode  IN  VARCHAR2 DEFAULT 'UPI',
        p_description   IN  VARCHAR2 DEFAULT NULL,
        p_txn_id        OUT VARCHAR2
    );

    PROCEDURE print_monthly_report (p_month IN DATE);

END pkg_budget;
/


-- ---------------------------------------------------------------------
-- 2. Package body (the actual code)
-- ---------------------------------------------------------------------
CREATE OR REPLACE PACKAGE BODY pkg_budget AS

    -- Give error -20004 a name so we can catch it with WHEN e_no_budget
    e_no_budget EXCEPTION;
    PRAGMA EXCEPTION_INIT(e_no_budget, -20004);


    -- Private helper: the category must exist AND be an expense category
    PROCEDURE assert_expense_category (p_category IN VARCHAR2) IS
        v_group categories.category_group%TYPE;
    BEGIN
        SELECT category_group
        INTO   v_group
        FROM   categories
        WHERE  category_name = p_category;

        IF v_group = 'Income' THEN
            RAISE_APPLICATION_ERROR(-20002,
                'Category "' || p_category || '" is an income category. Use an expense category.');
        END IF;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20001, 'Unknown category: "' || p_category || '"');
    END assert_expense_category;


    -- Private helper: amount must be positive and below the sanity limit
    PROCEDURE assert_valid_amount (p_amount IN NUMBER, p_what IN VARCHAR2) IS
    BEGIN
        IF p_amount IS NULL OR p_amount <= 0 THEN
            RAISE_APPLICATION_ERROR(-20005, p_what || ' must be greater than zero.');
        ELSIF p_amount > c_max_amount THEN
            RAISE_APPLICATION_ERROR(-20005, p_what || ' of ' || p_amount ||
                ' is above the limit of ' || c_max_amount || '. Please check the value.');
        END IF;
    END assert_valid_amount;


    FUNCTION get_budget_amount (p_month IN DATE, p_category IN VARCHAR2) RETURN NUMBER IS
        v_amount budgets.budget_amount%TYPE;
    BEGIN
        SELECT budget_amount
        INTO   v_amount
        FROM   budgets
        WHERE  budget_month = TRUNC(p_month, 'MM')
        AND    category     = p_category;
        RETURN v_amount;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20004, 'No budget defined for "' || p_category ||
                '" in ' || TO_CHAR(p_month, 'YYYY-MM'));
    END get_budget_amount;


    FUNCTION get_actual_spent (p_month IN DATE, p_category IN VARCHAR2) RETURN NUMBER IS
        v_total NUMBER;
    BEGIN
        -- Date range (first day of month up to, not including, next month)
        SELECT NVL(SUM(amount), 0)
        INTO   v_total
        FROM   transactions
        WHERE  category = p_category
        AND    txn_type = 'Debit'
        AND    txn_date >= TRUNC(p_month, 'MM')
        AND    txn_date <  ADD_MONTHS(TRUNC(p_month, 'MM'), 1);
        RETURN v_total;
    END get_actual_spent;


    FUNCTION get_utilisation_pct (p_month IN DATE, p_category IN VARCHAR2) RETURN NUMBER IS
    BEGIN
        -- budget_amount is always > 0 (CHECK constraint), so no divide-by-zero
        RETURN ROUND(get_actual_spent(p_month, p_category)
                     / get_budget_amount(p_month, p_category) * 100, 1);
    END get_utilisation_pct;


    FUNCTION get_budget_status (p_utilisation_pct IN NUMBER) RETURN VARCHAR2 IS
    BEGIN
        IF p_utilisation_pct IS NULL THEN
            RETURN NULL;
        ELSIF p_utilisation_pct > c_over_budget_pct THEN
            RETURN 'Over Budget';
        ELSIF p_utilisation_pct >= c_near_limit_pct THEN
            RETURN 'Near Limit';
        ELSE
            RETURN 'Within Budget';
        END IF;
    END get_budget_status;


    PROCEDURE validate_budget (p_month IN DATE, p_category IN VARCHAR2, p_amount IN NUMBER) IS
    BEGIN
        IF p_month IS NULL THEN
            RAISE_APPLICATION_ERROR(-20003, 'Budget month is required.');
        END IF;
        assert_expense_category(p_category);
        assert_valid_amount(p_amount, 'Budget amount');
    END validate_budget;


    PROCEDURE set_budget (p_month IN DATE, p_category IN VARCHAR2, p_amount IN NUMBER) IS
    BEGIN
        validate_budget(p_month, p_category, p_amount);

        -- MERGE = "update if it exists, otherwise insert" (an upsert)
        MERGE INTO budgets b
        USING (SELECT TRUNC(p_month, 'MM') AS m, p_category AS c, ROUND(p_amount, 2) AS a
               FROM dual) s
        ON    (b.budget_month = s.m AND b.category = s.c)
        WHEN MATCHED THEN
            UPDATE SET b.budget_amount = s.a
        WHEN NOT MATCHED THEN
            INSERT (budget_month, category, budget_amount) VALUES (s.m, s.c, s.a);

        DBMS_OUTPUT.PUT_LINE('Budget saved: ' || p_category || ' ' ||
                             TO_CHAR(p_month, 'YYYY-MM') || ' = ' || ROUND(p_amount, 2));
    END set_budget;


    PROCEDURE check_budget (p_month IN DATE, p_category IN VARCHAR2) IS
        v_month   DATE := TRUNC(p_month, 'MM');
        v_budget  NUMBER;
        v_actual  NUMBER;
        v_pct     NUMBER;
        v_status  VARCHAR2(15);
    BEGIN
        v_budget := get_budget_amount(v_month, p_category);
        v_actual := get_actual_spent(v_month, p_category);
        v_pct    := ROUND(v_actual / v_budget * 100, 1);
        v_status := get_budget_status(v_pct);

        -- Same rule as the Python dashboard: no alert for a fixed bill
        -- paid exactly as planned (e.g. rent = budget -> 100% but expected)
        IF v_status <> 'Within Budget' AND v_actual <> v_budget THEN
            INSERT INTO budget_alerts (budget_month, category, budget_amount,
                                       actual_spent, utilisation_pct, status)
            VALUES (v_month, p_category, v_budget, v_actual, v_pct, v_status);

            DBMS_OUTPUT.PUT_LINE('ALERT (' || v_status || '): ' || p_category || ' ' ||
                                 TO_CHAR(v_month, 'YYYY-MM') || ' spent ' || v_actual ||
                                 ' of ' || v_budget || ' (' || v_pct || '%)');
        ELSE
            DBMS_OUTPUT.PUT_LINE('OK: ' || p_category || ' ' || TO_CHAR(v_month, 'YYYY-MM') ||
                                 ' at ' || v_pct || '% of budget (' || v_status || ')');
        END IF;
    EXCEPTION
        WHEN e_no_budget THEN
            -- Not an error for the caller: there is simply nothing to compare
            DBMS_OUTPUT.PUT_LINE('No budget set for ' || p_category || ' in ' ||
                                 TO_CHAR(v_month, 'YYYY-MM') || ' - alert check skipped.');
    END check_budget;


    PROCEDURE record_expense (
        p_txn_date      IN  DATE,
        p_category      IN  VARCHAR2,
        p_amount        IN  NUMBER,
        p_merchant      IN  VARCHAR2,
        p_payment_mode  IN  VARCHAR2 DEFAULT 'UPI',
        p_description   IN  VARCHAR2 DEFAULT NULL,
        p_txn_id        OUT VARCHAR2
    ) IS
    BEGIN
        -- ---- validation (same rules as the Streamlit "Add Expense" form) ----
        IF p_txn_date IS NULL OR TRUNC(p_txn_date) > TRUNC(SYSDATE) THEN
            RAISE_APPLICATION_ERROR(-20006, 'Expense date is missing or in the future.');
        END IF;
        assert_expense_category(p_category);
        assert_valid_amount(p_amount, 'Expense amount');
        IF p_payment_mode IS NULL
           OR p_payment_mode NOT IN ('UPI', 'Debit Card', 'Credit Card', 'Net Banking', 'Cash') THEN
            RAISE_APPLICATION_ERROR(-20007, 'Invalid payment mode: "' || p_payment_mode || '"');
        END IF;
        IF TRIM(p_merchant) IS NULL THEN
            RAISE_APPLICATION_ERROR(-20008, 'Merchant / payee is required.');
        END IF;

        -- ---- insert: ID, year_month, day_of_week, is_weekend come from the trigger ----
        INSERT INTO transactions (txn_date, description, category, amount,
                                  txn_type, payment_mode, merchant)
        VALUES (TRUNC(p_txn_date),
                SUBSTR(NVL(p_description, 'Manual entry - ' || TRIM(p_merchant)), 1, 100),
                p_category,
                ROUND(p_amount, 2),
                'Debit',
                p_payment_mode,
                SUBSTR(TRIM(p_merchant), 1, 60))
        RETURNING transaction_id INTO p_txn_id;

        DBMS_OUTPUT.PUT_LINE('Expense recorded: ' || p_txn_id || ' - ' || p_category ||
                             ' ' || ROUND(p_amount, 2));

        -- ---- re-check this category's budget for that month ----
        check_budget(p_txn_date, p_category);
    END record_expense;


    PROCEDURE print_monthly_report (p_month IN DATE) IS
        -- Explicit cursor with a parameter: one row per budgeted category
        CURSOR c_report (cp_month DATE) IS
            SELECT b.category,
                   b.budget_amount,
                   NVL(SUM(t.amount), 0) AS actual_spent
            FROM   budgets b
            LEFT JOIN transactions t
                   ON  t.category = b.category
                   AND t.txn_type = 'Debit'
                   AND t.txn_date >= b.budget_month
                   AND t.txn_date <  ADD_MONTHS(b.budget_month, 1)
            WHERE  b.budget_month = cp_month
            GROUP  BY b.category, b.budget_amount
            ORDER  BY NVL(SUM(t.amount), 0) / b.budget_amount DESC;

        v_row           c_report%ROWTYPE;
        v_pct           NUMBER;
        v_total_budget  NUMBER := 0;
        v_total_actual  NUMBER := 0;
        v_over          PLS_INTEGER := 0;
        v_near          PLS_INTEGER := 0;
    BEGIN
        DBMS_OUTPUT.PUT_LINE('BUDGET REPORT FOR ' || TO_CHAR(p_month, 'YYYY-MM'));
        DBMS_OUTPUT.PUT_LINE(RPAD('Category', 16) || LPAD('Budget', 12) || LPAD('Spent', 12) ||
                             LPAD('Used %', 9) || '  Status');
        DBMS_OUTPUT.PUT_LINE(RPAD('-', 64, '-'));

        OPEN c_report(TRUNC(p_month, 'MM'));
        LOOP
            FETCH c_report INTO v_row;
            EXIT WHEN c_report%NOTFOUND;

            v_pct := ROUND(v_row.actual_spent / v_row.budget_amount * 100, 1);
            v_total_budget := v_total_budget + v_row.budget_amount;
            v_total_actual := v_total_actual + v_row.actual_spent;
            IF get_budget_status(v_pct) = 'Over Budget' THEN v_over := v_over + 1; END IF;
            IF get_budget_status(v_pct) = 'Near Limit'  THEN v_near := v_near + 1; END IF;

            DBMS_OUTPUT.PUT_LINE(RPAD(v_row.category, 16) ||
                                 LPAD(TO_CHAR(v_row.budget_amount, 'FM999,999,990'), 12) ||
                                 LPAD(TO_CHAR(v_row.actual_spent,  'FM999,999,990.00'), 12) ||
                                 LPAD(TO_CHAR(v_pct, 'FM9990.0'), 9) || '  ' ||
                                 get_budget_status(v_pct));
        END LOOP;

        IF c_report%ROWCOUNT = 0 THEN
            DBMS_OUTPUT.PUT_LINE('No budget found for this month.');
        ELSE
            DBMS_OUTPUT.PUT_LINE(RPAD('-', 64, '-'));
            DBMS_OUTPUT.PUT_LINE(RPAD('TOTAL', 16) ||
                                 LPAD(TO_CHAR(v_total_budget, 'FM999,999,990'), 12) ||
                                 LPAD(TO_CHAR(v_total_actual, 'FM999,999,990.00'), 12) ||
                                 LPAD(TO_CHAR(ROUND(v_total_actual / v_total_budget * 100, 1), 'FM9990.0'), 9));
            DBMS_OUTPUT.PUT_LINE(v_over || ' categories over budget, ' || v_near || ' near the limit.');
        END IF;
        CLOSE c_report;
    END print_monthly_report;

END pkg_budget;
/


-- ---------------------------------------------------------------------
-- 3. Confirm the package compiled. EXPECTED: both rows VALID.
--    If INVALID, run:  SELECT * FROM user_errors WHERE name = 'PKG_BUDGET';
-- ---------------------------------------------------------------------
SELECT object_name, object_type, status
FROM   user_objects
WHERE  object_name = 'PKG_BUDGET';


-- ---------------------------------------------------------------------
-- 4. Using the functions inside a normal SQL query
--    EXPECTED for 2025-10 (first rows): Shopping 214.1 Over Budget,
--    Travel 163 Over Budget, Food and Dining 147.4 Over Budget ...
-- ---------------------------------------------------------------------
SELECT category,
       budget_amount,
       pkg_budget.get_actual_spent(budget_month, category)                                AS actual_spent,
       pkg_budget.get_utilisation_pct(budget_month, category)                             AS utilisation_pct,
       pkg_budget.get_budget_status(pkg_budget.get_utilisation_pct(budget_month, category)) AS status
FROM   budgets
WHERE  budget_month = DATE '2025-10-01'
ORDER  BY utilisation_pct DESC;


-- ---------------------------------------------------------------------
-- 5. Demonstration block. Everything is ROLLED BACK at the end, so your
--    data is unchanged after running it.
--    EXPECTED output (summary):
--      * Shopping 2025-10 utilisation = 214.1 -> Over Budget
--      * Report for 2025-10: TOTAL budget 62,950, spent 71,274.71,
--        "5 categories over budget, 3 near the limit."
--      * Three validation errors caught: ORA-20005, ORA-20002, ORA-20001
--      * New Shopping expense of 1500 on 2025-12-20: Shopping Dec 2025
--        goes from 99.9% to 121.4% -> "ALERT (Over Budget)"
-- ---------------------------------------------------------------------
DECLARE
    v_txn_id  transactions.transaction_id%TYPE;
    v_pct     NUMBER;
BEGIN
    -- (a) utilisation + status for one category
    v_pct := pkg_budget.get_utilisation_pct(DATE '2025-10-01', 'Shopping');
    DBMS_OUTPUT.PUT_LINE('(a) Shopping 2025-10: ' || v_pct || '% -> ' ||
                         pkg_budget.get_budget_status(v_pct));
    DBMS_OUTPUT.PUT_LINE('');

    -- (b) full monthly report (cursor)
    pkg_budget.print_monthly_report(DATE '2025-10-01');
    DBMS_OUTPUT.PUT_LINE('');

    -- (c) validation: negative budget must be rejected
    BEGIN
        pkg_budget.set_budget(DATE '2026-01-01', 'Shopping', -500);
    EXCEPTION
        WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('(c) Rejected as expected: ' || SQLERRM);
    END;

    -- (d) validation: an income category cannot be an expense
    BEGIN
        pkg_budget.record_expense(DATE '2025-12-20', 'Salary', 1000, 'Test', 'UPI', NULL, v_txn_id);
    EXCEPTION
        WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('(d) Rejected as expected: ' || SQLERRM);
    END;

    -- (e) validation: unknown category
    BEGIN
        pkg_budget.record_expense(DATE '2025-12-20', 'Gym', 1000, 'Test', 'UPI', NULL, v_txn_id);
    EXCEPTION
        WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('(e) Rejected as expected: ' || SQLERRM);
    END;
    DBMS_OUTPUT.PUT_LINE('');

    -- (f) a valid expense that pushes Shopping (Dec 2025) over budget
    DBMS_OUTPUT.PUT_LINE('(f) Before: Shopping 2025-12 at ' ||
                         pkg_budget.get_utilisation_pct(DATE '2025-12-01', 'Shopping') || '%');
    pkg_budget.record_expense(DATE '2025-12-20', 'Shopping', 1500, 'Croma', 'Credit Card',
                              'Headphones - year-end sale', v_txn_id);

    -- (g) undo everything the demo changed
    ROLLBACK;
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Demo finished - all changes rolled back.');
END;
/
