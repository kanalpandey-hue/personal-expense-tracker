"""
data_cleaning.py
----------------
Cleans the raw bank-transaction export and adds useful analysis columns.

Cleaning steps (each one is logged with how many rows were affected):
    1. Remove duplicate transactions
    2. Standardise dates written in different formats
    3. Convert text amounts ("₹1,250.00") to numbers and fix negative signs
    4. Standardise transaction type (DR/CR -> Debit/Credit)
    5. Standardise category names (case, spaces, "and" vs "&")
    6. Fill missing categories using the merchant name
    7. Fill missing payment modes with "Unknown"
    8. Detect data-entry errors (extreme outliers) and remove them
    9. Feature engineering (month, weekday, expense type, etc.)

Run:  python src/data_cleaning.py
"""

from datetime import datetime

import numpy as np
import pandas as pd

import config


class CleaningLog:
    """Small helper that records what each cleaning step did."""

    def __init__(self):
        self.lines = []

    def add(self, message):
        print("  -", message)
        self.lines.append(message)

    def save(self, path):
        header = f"DATA CLEANING LOG  (generated {datetime.now():%Y-%m-%d %H:%M})\n" + "=" * 60 + "\n"
        path.write_text(header + "\n".join(f"- {line}" for line in self.lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"]


def parse_date(text):
    """
    Try each known date format one by one.
    Returns a datetime, or NaT (Not a Time) if no format matches.
    We list formats explicitly instead of letting pandas guess, because
    guessing can confuse 05/01 (5 Jan) with 01/05 (1 May).
    """
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(text).strip(), fmt)
        except ValueError:
            continue
    return pd.NaT


def parse_amount(value):
    """Turn '₹1,250.00' or '1250' or 1250.0 into the float 1250.0."""
    if pd.isna(value):
        return np.nan
    text = str(value).replace("₹", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return np.nan


# Map any lower-case, trimmed spelling to the official category name
OFFICIAL_CATEGORIES = config.EXPENSE_CATEGORIES + config.INCOME_CATEGORIES
CATEGORY_LOOKUP = {}
for name in OFFICIAL_CATEGORIES:
    CATEGORY_LOOKUP[name.lower()] = name
    CATEGORY_LOOKUP[name.lower().replace("&", "and")] = name


def standardise_category(value):
    if pd.isna(value):
        return np.nan
    key = " ".join(str(value).strip().lower().split())  # trim + collapse spaces
    return CATEGORY_LOOKUP.get(key, np.nan)


# Essential = needs; Discretionary = wants (used in the 50/30/20 analysis)
ESSENTIAL = {"Rent", "Groceries", "Utilities", "Healthcare", "Insurance", "Transportation", "Education"}
FIXED = {"Rent", "Subscriptions", "Insurance", "Utilities"}


def add_features(df):
    """
    Add the extra analysis columns (month, weekday, expense type, ...).
    Kept as a separate function so the dashboard can reuse it for
    expenses the user adds manually.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.strftime("%b")
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    df["quarter"] = "Q" + df["date"].dt.quarter.astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["is_weekend"] = df["date"].dt.day_of_week >= 5
    # signed_amount: income positive, expense negative -> easy cash-flow sums
    df["signed_amount"] = np.where(df["txn_type"] == "Credit", df["amount"], -df["amount"])
    df["expense_type"] = np.select(
        [df["txn_type"] == "Credit", df["category"].isin(ESSENTIAL)],
        ["Income", "Essential"],
        default="Discretionary",
    )
    df["cost_nature"] = np.where(df["category"].isin(FIXED), "Fixed", "Variable")
    df.loc[df["txn_type"] == "Credit", "cost_nature"] = "Income"
    return df


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------
def clean_transactions(raw):
    log = CleaningLog()
    df = raw.copy()
    log.add(f"Loaded raw data: {len(df):,} rows, {df.shape[1]} columns")

    # 1) Duplicates ---------------------------------------------------------
    before = len(df)
    df = df.drop_duplicates()
    # Same ID appearing twice is also a duplicate even if other text differs
    df = df.drop_duplicates(subset="transaction_id", keep="first")
    log.add(f"Removed {before - len(df)} duplicate rows")

    # 2) Dates --------------------------------------------------------------
    non_iso = (~df["date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")).sum()
    df["date"] = df["date"].apply(parse_date)
    bad_dates = df["date"].isna().sum()
    df = df.dropna(subset=["date"])
    log.add(f"Standardised {non_iso} dates written in non-ISO formats; dropped {bad_dates} unparseable dates")

    # 3) Amounts ------------------------------------------------------------
    text_amounts = df["amount"].astype(str).str.contains("₹|,", regex=True).sum()
    df["amount"] = df["amount"].apply(parse_amount)
    negatives = (df["amount"] < 0).sum()
    df["amount"] = df["amount"].abs()  # direction is stored in txn_type, so amount is always positive
    missing_amt = df["amount"].isna().sum()
    df = df.dropna(subset=["amount"])
    log.add(f"Converted {text_amounts} text amounts to numbers; fixed {negatives} negative amounts; "
            f"dropped {missing_amt} rows with no amount")

    # 4) Transaction type ---------------------------------------------------
    type_map = {"DR": "Debit", "CR": "Credit", "DEBIT": "Debit", "CREDIT": "Credit"}
    fixed_types = df["txn_type"].isin(["DR", "CR"]).sum()
    df["txn_type"] = df["txn_type"].str.strip().str.upper().map(type_map)
    log.add(f"Standardised {fixed_types} transaction-type labels (DR/CR -> Debit/Credit)")

    # 5) Category names -----------------------------------------------------
    original = df["category"].copy()
    df["category"] = df["category"].apply(standardise_category)
    changed = ((original != df["category"]) & original.notna()).sum()
    log.add(f"Standardised {changed} inconsistent category spellings")

    # 6) Missing categories -> use the merchant's most common category -----
    missing_cat = df["category"].isna().sum()
    merchant_to_category = (
        df.dropna(subset=["category"])
          .groupby("merchant")["category"]
          .agg(lambda s: s.mode().iloc[0])   # mode() = most frequent value
    )
    df["category"] = df["category"].fillna(df["merchant"].map(merchant_to_category))
    still_missing = df["category"].isna().sum()
    df["category"] = df["category"].fillna("Uncategorised")
    log.add(f"Filled {missing_cat - still_missing} of {missing_cat} missing categories using merchant name "
            f"({still_missing} left as 'Uncategorised')")

    # 7) Missing payment modes ---------------------------------------------
    missing_pm = df["payment_mode"].isna().sum()
    df["payment_mode"] = df["payment_mode"].fillna("Unknown")
    log.add(f"Filled {missing_pm} missing payment modes with 'Unknown' (not guessed, to stay honest)")

    # 8) Data-entry errors --------------------------------------------------
    # If a purchase is more than 20x that merchant's typical (median) amount,
    # it's almost certainly a typing error (e.g. ₹450 typed as ₹45,000).
    merchant_median = df.groupby("merchant")["amount"].transform("median")
    entry_errors = df["amount"] > 20 * merchant_median
    log.add(f"Removed {entry_errors.sum()} data-entry errors (amount > 20x merchant median): "
            + ", ".join(f"{m} ₹{a:,.0f}" for m, a in df.loc[entry_errors, ["merchant", "amount"]].values))
    df = df[~entry_errors]

    # Flag (but KEEP) genuine large spends using the IQR rule within each category.
    # These are real purchases (e.g. a laptop during Diwali) worth highlighting.
    def iqr_flag(group):
        q1, q3 = group.quantile(0.25), group.quantile(0.75)
        return group > q3 + 1.5 * (q3 - q1)

    df["is_large_spend"] = df.groupby("category")["amount"].transform(iqr_flag)
    df.loc[df["txn_type"] == "Credit", "is_large_spend"] = False
    log.add(f"Flagged {int(df['is_large_spend'].sum())} genuine large spends using the IQR rule (kept in data)")

    # 9) Feature engineering ------------------------------------------------
    df = add_features(df)
    log.add("Added features: year, month, month_name, year_month, quarter, day_of_week, is_weekend, "
            "signed_amount, expense_type, cost_nature, is_large_spend")

    # Final tidy-up
    df["amount"] = df["amount"].round(2)
    df["signed_amount"] = df["signed_amount"].round(2)
    df = df.sort_values(["date", "transaction_id"]).reset_index(drop=True)
    log.add(f"Final clean data: {len(df):,} rows, {df.shape[1]} columns, "
            f"{df.isna().sum().sum()} missing values remaining")
    return df, log


def load_clean_data():
    """Helper used by other scripts to read the cleaned CSV with correct types."""
    return pd.read_csv(config.CLEAN_TRANSACTIONS_FILE, parse_dates=["date"])


def main():
    config.ensure_folders()
    print("Cleaning transactions...")
    raw = pd.read_csv(config.RAW_TRANSACTIONS_FILE)
    clean, log = clean_transactions(raw)
    clean.to_csv(config.CLEAN_TRANSACTIONS_FILE, index=False)
    log.save(config.CLEANING_LOG_FILE)
    print(f"Saved clean data -> {config.CLEAN_TRANSACTIONS_FILE}")
    print(f"Saved log        -> {config.CLEANING_LOG_FILE}")


if __name__ == "__main__":
    main()
