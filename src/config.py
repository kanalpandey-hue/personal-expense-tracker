"""
config.py
---------
Central place for all file paths and project settings.

Keeping paths in ONE file means that if we move a folder, we only
change it here instead of hunting through every script.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Folder paths
# ---------------------------------------------------------------------------
# Path(__file__) is this file -> .parent is "src" -> .parent again is project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
SQL_DIR = PROJECT_ROOT / "sql"

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
RAW_TRANSACTIONS_FILE = RAW_DIR / "transactions_raw.csv"
BUDGET_FILE = RAW_DIR / "monthly_budget.csv"
CLEAN_TRANSACTIONS_FILE = PROCESSED_DIR / "transactions_clean.csv"
# Expenses the user adds through the dashboard form are stored here
USER_ENTRIES_FILE = DATA_DIR / "user_entries.csv"
CLEANING_LOG_FILE = PROCESSED_DIR / "cleaning_log.txt"
DATABASE_FILE = PROCESSED_DIR / "expense_tracker.db"
EXCEL_REPORT_FILE = REPORTS_DIR / "Expense_Analysis_Report.xlsx"
SUMMARY_REPORT_FILE = REPORTS_DIR / "insights_summary.md"

# ---------------------------------------------------------------------------
# Business settings
# ---------------------------------------------------------------------------
# The 12 official expense categories used throughout the project.
EXPENSE_CATEGORIES = [
    "Rent",
    "Groceries",
    "Food & Dining",
    "Transportation",
    "Utilities",
    "Shopping",
    "Entertainment",
    "Healthcare",
    "Education",
    "Travel",
    "Subscriptions",
    "Insurance",
]

# Income categories (money coming IN).
INCOME_CATEGORIES = ["Salary", "Freelance", "Interest", "Refund"]

# Allowed payment modes (typical for an Indian bank customer).
PAYMENT_MODES = ["UPI", "Debit Card", "Credit Card", "Net Banking", "Cash"]

# Alert thresholds used by the budget tracker.
BUDGET_WARNING_PCT = 80    # "Near Limit" when 80% of a category budget is used
BUDGET_EXCEEDED_PCT = 100  # alert when budget is fully used

# Currency symbol for printing / charts
CURRENCY = "₹"


def ensure_folders():
    """Create every output folder if it does not exist yet."""
    for folder in [RAW_DIR, PROCESSED_DIR, REPORTS_DIR, FIGURES_DIR, SQL_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
