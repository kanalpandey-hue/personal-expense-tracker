"""
test_project.py - Automated checks that the project works correctly.

Run:  python -m pytest tests -v
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
import analysis  # noqa: E402
import config  # noqa: E402
import data_cleaning as dc  # noqa: E402


# ---------------------------------------------------------------------------
# Unit tests for the small cleaning helpers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("2024-01-05", "2024-01-05"),
    ("05/01/2024", "2024-01-05"),   # day/month/year -> 5 January, NOT 1 May
    ("05-Jan-2024", "2024-01-05"),
])
def test_parse_date_handles_all_formats(text, expected):
    assert dc.parse_date(text).strftime("%Y-%m-%d") == expected


def test_parse_date_returns_nat_for_garbage():
    assert pd.isna(dc.parse_date("not a date"))


@pytest.mark.parametrize("value, expected", [("₹1,250.50", 1250.5), ("300", 300.0), (99.9, 99.9)])
def test_parse_amount(value, expected):
    assert dc.parse_amount(value) == expected


@pytest.mark.parametrize("raw, expected", [
    ("GROCERIES", "Groceries"), (" Rent ", "Rent"),
    ("food and dining", "Food & Dining"), ("unknown thing", None),
])
def test_standardise_category(raw, expected):
    result = dc.standardise_category(raw)
    assert (pd.isna(result) and expected is None) or result == expected


def test_budget_status_thresholds():
    assert analysis.budget_status(50) == "Within Budget"
    assert analysis.budget_status(85) == "Near Limit"
    assert analysis.budget_status(100) == "Near Limit"
    assert analysis.budget_status(101) == "Over Budget"


# ---------------------------------------------------------------------------
# Data-quality tests on the cleaned file
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def clean():
    return analysis.load_transactions()


@pytest.fixture(scope="module")
def budget():
    return analysis.load_budget()


def test_clean_data_has_no_missing_values(clean):
    assert clean.isna().sum().sum() == 0


def test_no_duplicate_transaction_ids(clean):
    assert clean["transaction_id"].is_unique


def test_amounts_positive_and_types_valid(clean):
    assert (clean["amount"] > 0).all()
    assert set(clean["txn_type"]) == {"Debit", "Credit"}


def test_categories_are_official(clean):
    allowed = set(config.EXPENSE_CATEGORIES + config.INCOME_CATEGORIES)
    assert set(clean["category"]).issubset(allowed)


def test_debits_use_expense_categories(clean):
    assert set(clean.loc[clean["txn_type"] == "Debit", "category"]).issubset(config.EXPENSE_CATEGORIES)


# ---------------------------------------------------------------------------
# Analysis consistency tests
# ---------------------------------------------------------------------------
def test_kpis_add_up(clean):
    k = analysis.kpi_summary(clean)
    assert k["net_savings"] == pytest.approx(k["total_income"] - k["total_expense"], abs=0.01)


def test_monthly_summary_matches_total(clean):
    monthly = analysis.monthly_summary(clean)
    assert monthly["expense"].sum() == pytest.approx(analysis.kpi_summary(clean)["total_expense"], abs=1)


def test_category_shares_sum_to_100(clean):
    assert analysis.category_summary(clean)["share_pct"].sum() == pytest.approx(100, abs=0.1)


def test_budget_vs_actual_covers_every_budget_row(clean, budget):
    bva = analysis.budget_vs_actual(clean, budget)
    assert len(bva) == len(budget)
    assert (bva["variance"] == (bva["budget_amount"] - bva["actual_spent"]).round(2)).all()


def test_sql_matches_pandas(clean, budget):
    """The SQL query and the pandas code must give the same answer."""
    if not config.DATABASE_FILE.exists():
        pytest.skip("Run src/sql_analysis.py first")
    with sqlite3.connect(config.DATABASE_FILE) as conn:
        sql = pd.read_sql_query(
            "SELECT category, SUM(amount) AS total FROM transactions "
            "WHERE txn_type='Debit' GROUP BY category", conn).set_index("category")["total"]
    pandas_totals = analysis.category_summary(clean).set_index("category")["total_spent"]
    pd.testing.assert_series_equal(sql.sort_index().round(2), pandas_totals.sort_index().round(2),
                                   check_names=False)


def test_insights_are_generated(clean, budget):
    insights, recs = analysis.generate_insights(clean, budget)
    assert len(insights) >= 5 and len(recs) >= 2
