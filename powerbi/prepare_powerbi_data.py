"""
prepare_powerbi_data.py
-----------------------
Creates the 4 CSV files used by the Power BI dashboard, from the project's
EXISTING cleaned data. It only READS project files and writes new files
into powerbi/data/.

Star schema (2 fact tables + 2 lookup tables):

        months.csv ──┐                      ┌── categories.csv
     (1 row/month)   │                      │   (1 row/category)
                     ▼                      ▼
              transactions.csv      budget_vs_actual.csv
              (1 row/transaction)   (1 row/month + category)

    * months.year_month       -> links to year_month in both fact tables
    * categories.category     -> links to category   in both fact tables

Because both fact tables share the same two lookup tables, ONE Month
slicer and ONE Category slicer filter every chart on the page.

Run from the project folder:
    python powerbi/prepare_powerbi_data.py
"""

import sys
from pathlib import Path

import pandas as pd

POWERBI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = POWERBI_DIR.parent
OUTPUT_DIR = POWERBI_DIR / "data"

# Reuse the project's own code so numbers match the dashboard exactly
sys.path.append(str(PROJECT_ROOT / "src"))
import analysis  # noqa: E402
import config  # noqa: E402


def build_transactions(df):
    """Fact table 1: every transaction (income and expense)."""
    out = df[["transaction_id", "date", "year_month", "category", "merchant",
              "payment_mode", "txn_type", "amount", "day_of_week"]].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")   # format Power BI reads as a date
    return out.sort_values(["date", "transaction_id"])


def build_budget_vs_actual(df, budget):
    """Fact table 2: budget vs actual per month and category (existing project function)."""
    bva = analysis.budget_vs_actual(df, budget)
    return bva.rename(columns={"month": "year_month"})[
        ["year_month", "category", "budget_amount", "actual_spent", "variance", "utilisation_pct", "status"]]


def build_categories(df):
    """Lookup table: one row per category."""
    cats = (df[["category", "txn_type", "expense_type", "cost_nature"]]
            .drop_duplicates("category")
            .rename(columns={"expense_type": "category_group"}))
    # "Expense" or "Income" - easier to read than Debit/Credit in a slicer
    cats["category_type"] = cats["txn_type"].map({"Debit": "Expense", "Credit": "Income"})
    return cats[["category", "category_type", "category_group", "cost_nature"]].sort_values("category")


def build_months(df):
    """Lookup table: one row per month, with a few labels for charts."""
    months = pd.DataFrame({"year_month": sorted(df["year_month"].unique())})
    first_day = pd.to_datetime(months["year_month"] + "-01")
    months["year"] = first_day.dt.year
    months["quarter"] = "Q" + first_day.dt.quarter.astype(str)
    months["month_name"] = first_day.dt.strftime("%b")
    months["month_label"] = first_day.dt.strftime("%b %Y")   # e.g. "Jan 2024"
    return months


def check_star_schema(transactions, bva, categories, months):
    """Make sure every relationship in Power BI will work (no blank/unmatched rows)."""
    assert months["year_month"].is_unique, "months.year_month must be unique"
    assert categories["category"].is_unique, "categories.category must be unique"
    for name, fact in [("transactions", transactions), ("budget_vs_actual", bva)]:
        assert fact["year_month"].isin(months["year_month"]).all(), f"{name}: month missing from months.csv"
        assert fact["category"].isin(categories["category"]).all(), f"{name}: category missing from categories.csv"
        assert fact.notna().all().all(), f"{name}: contains blank values"
    print("Star schema check passed: all keys unique and every row has a matching month and category.")


def check_totals(df, transactions, bva):
    """Compare the Power BI files with the existing Python analysis."""
    kpi = analysis.kpi_summary(df)
    monthly = analysis.monthly_summary(df).set_index("year_month")

    # Monthly expense from transactions.csv vs analysis.monthly_summary()
    pbi_monthly = transactions[transactions["txn_type"] == "Debit"].groupby("year_month")["amount"].sum()
    assert (pbi_monthly.round(2) == monthly["expense"].round(2)).all(), "monthly expense mismatch"

    # Monthly 'actual' in budget_vs_actual.csv must equal the same monthly expense
    bva_monthly = bva.groupby("year_month")["actual_spent"].sum()
    assert (bva_monthly.round(2) == monthly["expense"].round(2)).all(), "budget actuals mismatch"

    income = transactions.loc[transactions["txn_type"] == "Credit", "amount"].sum()
    expense = transactions.loc[transactions["txn_type"] == "Debit", "amount"].sum()
    assert round(income, 2) == kpi["total_income"] and round(expense, 2) == kpi["total_expense"]

    print("Totals check passed: monthly expense and budget actuals match the Python analysis.\n")
    print("EXPECTED VALUES IN POWER BI (no filters applied):")
    print(f"  Total Income   : {income:,.2f}")
    print(f"  Total Expense  : {expense:,.2f}")
    print(f"  Net Savings    : {income - expense:,.2f}")
    print(f"  Savings Rate % : {(income - expense) / income * 100:.1f}")
    print(f"  Total Budget   : {bva['budget_amount'].sum():,.2f}")
    print(f"  Budget Used %  : {bva['actual_spent'].sum() / bva['budget_amount'].sum() * 100:.1f}")


def main():
    df = analysis.load_transactions()        # data/processed/transactions_clean.csv
    budget = analysis.load_budget()          # data/raw/monthly_budget.csv

    transactions = build_transactions(df)
    bva = build_budget_vs_actual(df, budget)
    categories = build_categories(df)
    months = build_months(df)

    check_star_schema(transactions, bva, categories, months)
    check_totals(df, transactions, bva)

    OUTPUT_DIR.mkdir(exist_ok=True)
    for name, table in [("transactions", transactions), ("budget_vs_actual", bva),
                        ("categories", categories), ("months", months)]:
        table.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
        print(f"  saved data/{name}.csv  ({len(table):,} rows)")


if __name__ == "__main__":
    main()
