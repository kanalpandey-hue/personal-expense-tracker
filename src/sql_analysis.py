"""
sql_analysis.py
---------------
Loads the cleaned data into a SQLite database and runs the business
queries written in sql/analysis_queries.sql.

SQLite is a database stored in a single file. It comes built into
Python (module `sqlite3`), so nothing extra needs installing.

Outputs:
    data/processed/expense_tracker.db      (the database file)
    reports/sql_outputs/<query_name>.csv   (result of every query)

Run:  python src/sql_analysis.py
"""

import sqlite3

import pandas as pd

import config

SQL_OUTPUT_DIR = config.REPORTS_DIR / "sql_outputs"


def build_database(conn):
    """Create the tables (schema.sql) and insert the cleaned data."""
    conn.executescript((config.SQL_DIR / "schema.sql").read_text(encoding="utf-8"))

    df = pd.read_csv(config.CLEAN_TRANSACTIONS_FILE)
    budget = pd.read_csv(config.BUDGET_FILE)

    # categories table: one row per category with its group & nature
    categories = (df[["category", "expense_type", "cost_nature"]]
                  .drop_duplicates("category")
                  .rename(columns={"category": "category_name", "expense_type": "category_group"}))
    categories.to_sql("categories", conn, if_exists="append", index=False)

    # transactions table: rename 'date' -> 'txn_date', store booleans as 0/1
    txns = df.rename(columns={"date": "txn_date"})[
        ["transaction_id", "txn_date", "year_month", "description", "category", "amount",
         "txn_type", "payment_mode", "merchant", "day_of_week", "is_weekend"]].copy()
    txns["is_weekend"] = txns["is_weekend"].astype(int)
    txns.to_sql("transactions", conn, if_exists="append", index=False)

    budget.to_sql("budgets", conn, if_exists="append", index=False)
    conn.commit()
    print(f"Database built: {len(txns):,} transactions, {len(budget):,} budget rows, "
          f"{len(categories)} categories")


def read_named_queries(path):
    """
    Split the .sql file into {query_name: sql_text}.
    Every query begins with a comment line like:  -- name: q01_monthly_cash_flow
    """
    queries = {}
    current_name = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("-- name:"):
            current_name = line.split(":", 1)[1].strip()
            queries[current_name] = []
        elif current_name:
            queries[current_name].append(line)
    return {name: "\n".join(lines).strip() for name, lines in queries.items()}


def run_all_queries(conn):
    """Run every query, print a preview and save the result as CSV."""
    SQL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, sql in read_named_queries(config.SQL_DIR / "analysis_queries.sql").items():
        result = pd.read_sql_query(sql, conn)
        result.to_csv(SQL_OUTPUT_DIR / f"{name}.csv", index=False)
        results[name] = result
        print(f"\n--- {name} ({len(result)} rows) ---")
        print(result.head(5).to_string(index=False))
    return results


def main():
    config.ensure_folders()
    # Delete an old database so every run starts fresh
    if config.DATABASE_FILE.exists():
        config.DATABASE_FILE.unlink()
    with sqlite3.connect(config.DATABASE_FILE) as conn:
        build_database(conn)
        run_all_queries(conn)
    print(f"\nSQL results saved in {SQL_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
