# Oracle SQL & PL/SQL scripts

These scripts are the Oracle version (19c or later) of the project's SQLite scripts in `sql/`. The originals, and all Python and Streamlit files, are unchanged. The Python project still uses SQLite.

> **Testing status (please read):** these scripts have **not yet been run on an Oracle database**. No Oracle instance was available when they were written. They were checked in these ways instead:
> 1. Every plain SQL statement was parsed with the `sqlglot` Oracle dialect: 61 statements, 0 errors. This is a syntax sanity check; `sqlglot` is more lenient than Oracle.
> 2. A scan found no features newer than 19c (`IF EXISTS`, `GROUP BY` alias, `BOOLEAN`, …) and no SQLite leftovers (`TEXT`, `REAL`, `LIMIT`).
> 3. Logic check: all 10 queries in `05_analysis_queries.sql` were translated back to SQLite and run on the same data. **All 10 gave results identical** to the original queries in `reports/sql_outputs/`.
> 4. The two views in `06_create_views.sql` were checked the same way. All 6 check queries returned exactly the expected values written in that file.
>
> The PL/SQL in `04_budget_plsql.sql` and the trigger in `01_create_schema.sql` could not be checked by any tool. They will only be verified once you run them on Oracle. Each script ends with queries whose **expected results** are written in comments, so you can confirm everything in Live SQL yourself.

---

## Files and run order

| Order | File | What it does |
|---|---|---|
| 1 | `01_create_schema.sql` | Drops old objects, then creates 2 sequences, 4 tables, 1 trigger and 5 indexes |
| 2 | `02_insert_reference_data.sql` | Loads 16 categories and 288 monthly budget rows |
| 3 | `03_insert_transactions.sql` | Loads all 1,275 cleaned transactions |
| 4 | `04_budget_plsql.sql` | Creates the `PKG_BUDGET` package (budget validation and utilisation) and runs a demo |
| 5 | `05_analysis_queries.sql` | The 10 business questions, in Oracle syntax, each with its expected result |
| 6 | `06_create_views.sql` | Creates 2 views, `v_monthly_summary` and `v_budget_status`, plus check queries |
| – | `generate_oracle_inserts.py` | Rebuilds files 2 and 3 from the project CSVs (run only if the data changes) |

**Dependencies:** 02 and 03 need the tables from 01. 04, 05 and 06 need the data from 02 and 03. Files 04, 05 and 06 do not depend on each other, but running them in number order keeps things simple.

### 1. `01_create_schema.sql`: database design

| Object | Purpose |
|---|---|
| `categories` | Lookup table: 16 categories with group (Income / Essential / Discretionary) and nature (Income / Fixed / Variable) |
| `transactions` | Every cleaned transaction: real `DATE`, `NUMBER(12,2)` amount, `VARCHAR2` text |
| `budgets` | Planned budget per month per category. `budget_month` is a `DATE` that is always the 1st of the month |
| `budget_alerts` | Log of Near Limit / Over Budget alerts written by the PL/SQL package |
| `txn_seq` | Generates IDs for new transactions (`TXN100001`, …). Starts at 100001, so it never clashes with the loaded IDs `TXN000001`–`TXN001278` |
| `alert_seq` | Primary key for `budget_alerts` (used as a column `DEFAULT`, Oracle 12c+) |
| `trg_transactions_derive` | Fills `year_month`, `day_of_week` and `is_weekend` from `txn_date`, so they can never be wrong. It also assigns an ID from `txn_seq` when none is given |

**Constraints:** primary keys, foreign keys (transaction → category, budget → category, alert → budget), `CHECK`s on transaction type, payment mode, amount ≥ 0, budget > 0, weekend flag 0/1, `YYYY-MM` format (`REGEXP_LIKE`), and budget month = first day of the month.

**Mapping from the SQLite version**

| SQLite (`sql/schema.sql`) | Oracle | Why |
|---|---|---|
| `TEXT` | `VARCHAR2(n)` | Oracle has no `TEXT` type |
| `REAL` | `NUMBER(12,2)` | Exact decimals for money, no floating-point rounding |
| `txn_date DATE` (stored as text) | `txn_date DATE` (real date) | Date arithmetic and range filters work properly |
| `budgets.month TEXT '2024-01'` | `budgets.budget_month DATE '2024-01-01'` | Proper date type; enables `ADD_MONTHS` date-range joins |
| `is_weekend INTEGER` | `NUMBER(1)` + `CHECK (0,1)` | Oracle 19c has no SQL `BOOLEAN` |
| `DROP TABLE IF EXISTS` | PL/SQL loop over `user_objects` | `IF EXISTS` only exists from Oracle 23ai |
| — | sequences, trigger, `budget_alerts` table | New, needed by the PL/SQL part |

The **dataset structure is unchanged**. `transactions` has the same 11 columns as before, and the categories and budgets contain the same values.

### 2 & 3. Insert scripts (generated)

- These scripts use `INSERT ALL … SELECT 1 FROM dual`, which inserts 100 rows per statement (Oracle allows at most 999 target columns per `INSERT ALL`; 100 × 8 = 800). Live SQL then runs about 20 statements instead of about 1,500.
- Dates use ANSI literals (`DATE '2024-01-05'`), so they work under any NLS date setting.
- Apostrophes are escaped (`'Haldiram''s'`).
- `&` is written as `CHR(38)` (`'Food ' || CHR(38) || ' Dining'`). Otherwise SQL Developer and SQL*Plus would prompt for a "substitution variable".
- Only the 8 source columns are inserted. The trigger fills the 3 derived columns.
- Each script ends with verification queries and their **expected** results.

### 4. `04_budget_plsql.sql`: package `PKG_BUDGET`

| Member | Type | What it does |
|---|---|---|
| `get_budget_amount(month, category)` | function | Planned budget. Raises `ORA-20004` if none exists |
| `get_actual_spent(month, category)` | function | Sum of debits in that month (date-range filter) |
| `get_utilisation_pct(month, category)` | function | actual ÷ budget × 100, rounded to 1 decimal |
| `get_budget_status(pct)` | function | `> 100` Over Budget · `≥ 80` Near Limit · else Within Budget (same as `src/config.py`) |
| `validate_budget(month, category, amount)` | procedure | Month present, category exists and is not income, amount between 0 and ₹10 lakh |
| `set_budget(month, category, amount)` | procedure | Validates, then `MERGE` (inserts the budget or updates it if it already exists) |
| `check_budget(month, category)` | procedure | Computes utilisation and writes to `budget_alerts` when Near Limit / Over Budget. Like the dashboard, it skips fixed bills paid exactly as budgeted |
| `record_expense(...)` | procedure | Validates (date not in future, expense category, amount, payment mode, merchant), inserts, returns the new ID (`RETURNING … INTO`), then calls `check_budget` |
| `print_monthly_report(month)` | procedure | Budget vs actual table using an explicit parameterised **cursor** |

PL/SQL concepts covered: package spec and body, constants, `%TYPE` / `%ROWTYPE`, explicit cursor (`OPEN/FETCH/CLOSE`, `%NOTFOUND`, `%ROWCOUNT`), `NO_DATA_FOUND` handling, user-defined exceptions with `PRAGMA EXCEPTION_INIT`, `RAISE_APPLICATION_ERROR`, `MERGE`, `RETURNING INTO`, and calling package functions from SQL.

**Custom error codes:** `-20001` unknown category · `-20002` income category used as an expense · `-20003` month missing · `-20004` no budget · `-20005` invalid amount · `-20006` invalid/future date · `-20007` invalid payment mode · `-20008` merchant missing.

The procedures **do not COMMIT**; the caller decides. The demo block at the end ends with `ROLLBACK`, so running it leaves your data unchanged. Sequence numbers are not rolled back, so the next ID may skip a number; this is normal in Oracle.

### 5. `05_analysis_queries.sql`: 10 business questions

| # | Question | Oracle features used |
|---|---|---|
| Q1 | Monthly income, expense, savings | `CASE` inside `SUM` |
| Q2 | Spend and share per category | scalar subquery, `NULLIF` |
| Q3 | Budget vs actual per month & category | `LEFT JOIN` on a date range with `ADD_MONTHS`, `NVL`, `TO_CHAR` |
| Q4 | Months over budget per category | CTE (`WITH`) |
| Q5 | Payment-mode usage | aggregate + share % |
| Q6 | Top 10 merchants | `FETCH FIRST 10 ROWS ONLY` (replaces `LIMIT`) |
| Q7 | Weekend vs weekday | `GROUP BY` full `CASE` expression (19c can't group by alias) |
| Q8 | Month-over-month change | `LAG()` window function |
| Q9 | Top 5 categories per year | `RANK() OVER (PARTITION BY …)`, `EXTRACT(YEAR …)` |
| Q10 | Needs vs wants per year | `JOIN` + `EXTRACT` |

Rows with exactly equal values (e.g. two categories both at 0% in Q3) may appear in a different order in Oracle. This is normal, because SQL does not guarantee the order of ties.

Every query has an **`EXPECTED:`** comment above it, showing the row count and key rows. The values come from the verified project outputs in `reports/sql_outputs/`. Oracle hides trailing zeros, so `68000.00` appears as `68000`.

### 6. `06_create_views.sql`: two views

A **view** is a saved query with a name. It stores no data itself; Oracle runs the query every time you select from the view, so it always shows the latest data.

| View | Columns | Use it for |
|---|---|---|
| `v_monthly_summary` | `year_month`, `total_income`, `total_expense`, `net_savings`, `savings_rate_pct` | Monthly cash flow (one row per month) |
| `v_budget_status` | `year_month`, `category`, `budget_amount`, `actual_spent`, `remaining_budget`, `utilisation_pct`, `status` | Budget tracking (one row per month and category). `remaining_budget` < 0 means overspent |

Both views are plain SQL (no PL/SQL). `v_budget_status` uses the same status rules as the Python project and `PKG_BUDGET`. Example queries:

```sql
SELECT * FROM v_monthly_summary ORDER BY year_month;
SELECT * FROM v_budget_status WHERE status = 'Over Budget' ORDER BY year_month, category;
```

---

## How to run in Oracle Live SQL

Oracle Live SQL is free and runs in the browser, so nothing needs installing. Oracle has been redesigning the site, so button names may differ slightly from these steps.

1. Go to **https://livesql.oracle.com** and sign in with a free Oracle account. Create one if you need to.
2. Open the **SQL Worksheet**.
3. Optional: check the database version with
   `SELECT product, version FROM product_component_version;`
4. Open `01_create_schema.sql` in a text editor, copy **all** of it, paste it into the worksheet, and click **Run** (run the whole script, not just the current statement).
   - Expected: the final query lists 4 tables, 2 sequences and 1 trigger, all `VALID`.
5. Clear the worksheet. Paste and run `02_insert_reference_data.sql`.
   - Expected: `categories = 16`, `budget_rows = 288`, `total_budget = 1,502,800.00`.
6. Clear the worksheet. Paste and run `03_insert_transactions.sql` (about 300 KB).
   - Expected: `Credit 54 rows 1,883,674.03` · `Debit 1221 rows 1,460,802.19` · `weekend_rows = 367`, `missing_derived = 0`.
   - If the worksheet rejects a script this large or times out, paste it in two or three parts. Each `INSERT ALL … SELECT 1 FROM dual;` block is a complete statement, so split only between blocks, and make sure the final part includes `COMMIT;`.
7. Clear the worksheet. Paste and run `04_budget_plsql.sql`.
   - The demo prints messages with `DBMS_OUTPUT`. If no messages appear, open the worksheet's output panel (often called *DBMS Output*), or add `SET SERVEROUTPUT ON` as the first line and run again.
   - Expected: `PKG_BUDGET` package and package body both `VALID`. The utilisation query shows Shopping at 214.1 (Over Budget) for Oct 2025. The demo output shows the October 2025 report (total budget 62,950, spent 71,274.71, "5 categories over budget, 3 near the limit"), three rejected validations (`ORA-20005`, `ORA-20002`, `ORA-20001`), and `ALERT (Over Budget): Shopping 2025-12 … (121.4%)`.
   - If it says `INVALID`, run `SELECT line, position, text FROM user_errors WHERE name = 'PKG_BUDGET' ORDER BY sequence;` and share the output.
8. Clear the worksheet. Paste and run `05_analysis_queries.sql`, or run one query at a time.
   - Compare each result with the **`EXPECTED:`** comment above that query, e.g. Q4: Shopping is over budget in 16 of 24 months.
9. Clear the worksheet. Paste and run `06_create_views.sql`.
   - Expected: both views `VALID`; 24 monthly rows; deficit months 2024-07 and 2025-03; status counts Near Limit 101, Over Budget 94, Within Budget 93; budget totals 1,502,800 / 1,460,802.19 / 41,997.81.

Your tables and views stay in your Live SQL schema between sessions. To start fresh, re-run steps 4–9 in order, since step 4 drops all the tables first.

### Using the package yourself

```sql
-- Record an expense (date must not be in the future)
DECLARE
    v_id VARCHAR2(12);
BEGIN
    pkg_budget.record_expense(DATE '2025-12-28', 'Entertainment', 800, 'PVR Cinemas',
                              'UPI', 'Movie night', v_id);
    COMMIT;
END;
/

-- Set or change a budget
BEGIN
    pkg_budget.set_budget(DATE '2026-01-01', 'Shopping', 7500);
    COMMIT;
END;
/

-- Monthly report
BEGIN
    pkg_budget.print_monthly_report(DATE '2025-11-01');
END;
/

-- Alerts logged so far
SELECT * FROM budget_alerts ORDER BY created_at DESC;
```

### Running with SQL Developer or SQL*Plus instead

```sql
SET SERVEROUTPUT ON
@01_create_schema.sql
@02_insert_reference_data.sql
@03_insert_transactions.sql
@04_budget_plsql.sql
@05_analysis_queries.sql
@06_create_views.sql
```

### Regenerating the insert scripts

Only needed if the CSV data changes (for example after re-running `python main.py` with different settings):

```bash
python sql/oracle/generate_oracle_inserts.py
```
