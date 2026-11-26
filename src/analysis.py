"""
analysis.py
-----------
All the calculations of the project live here, as small reusable functions.

The Streamlit dashboard, the chart script and the Excel report all call these
same functions, so every number shown anywhere in the project is calculated
in ONE place (no copy-paste maths that could disagree).

Run:  python src/analysis.py   -> prints a full text summary
"""

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_transactions():
    return pd.read_csv(config.CLEAN_TRANSACTIONS_FILE, parse_dates=["date"])


def load_budget():
    return pd.read_csv(config.BUDGET_FILE)


def expenses_only(df):
    """Keep only money going OUT (debits)."""
    return df[df["txn_type"] == "Debit"]


def income_only(df):
    """Keep only money coming IN (credits)."""
    return df[df["txn_type"] == "Credit"]


# ---------------------------------------------------------------------------
# Key Performance Indicators (KPIs)
# ---------------------------------------------------------------------------
def kpi_summary(df):
    """Return the headline numbers as a dictionary."""
    expenses = expenses_only(df)
    income = income_only(df)
    total_income = income["amount"].sum()
    total_expense = expenses["amount"].sum()
    net_savings = total_income - total_expense
    months = df["year_month"].nunique()

    # Guard against division by zero when a filter leaves no income rows
    savings_rate = (net_savings / total_income * 100) if total_income else 0.0
    top_category = (expenses.groupby("category")["amount"].sum().idxmax()
                    if not expenses.empty else "-")

    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net_savings": round(net_savings, 2),
        "savings_rate_pct": round(savings_rate, 1),
        "months_covered": months,
        "avg_monthly_income": round(total_income / months, 2) if months else 0,
        "avg_monthly_expense": round(total_expense / months, 2) if months else 0,
        "num_transactions": len(df),
        "num_expense_txns": len(expenses),
        "avg_transaction_value": round(expenses["amount"].mean(), 2) if len(expenses) else 0,
        "top_spending_category": top_category,
    }


# ---------------------------------------------------------------------------
# Time-based summaries
# ---------------------------------------------------------------------------
def monthly_summary(df):
    """Income, expense, savings and savings-rate for every month."""
    # pivot_table turns Debit/Credit rows into two columns per month
    table = df.pivot_table(index="year_month", columns="txn_type", values="amount",
                           aggfunc="sum", fill_value=0)
    table = table.rename(columns={"Credit": "income", "Debit": "expense"})
    for col in ("income", "expense"):          # make sure both columns exist
        if col not in table:
            table[col] = 0.0
    table = table[["income", "expense"]]
    table["savings"] = table["income"] - table["expense"]
    table["savings_rate_pct"] = (table["savings"] / table["income"].where(table["income"] > 0) * 100).round(1)
    # Month-over-month % change in spending
    table["expense_mom_change_pct"] = (table["expense"].pct_change() * 100).round(1)
    # Cumulative savings shows how the bank balance grows over time
    table["cumulative_savings"] = table["savings"].cumsum()
    return table.round(2).reset_index()


def category_summary(df):
    """Total, average, count and share (%) of spending per category."""
    expenses = expenses_only(df)
    months = df["year_month"].nunique() or 1
    summary = expenses.groupby("category")["amount"].agg(
        total_spent="sum", num_transactions="count", avg_transaction="mean")
    summary["avg_per_month"] = summary["total_spent"] / months
    summary["share_pct"] = summary["total_spent"] / summary["total_spent"].sum() * 100
    return summary.sort_values("total_spent", ascending=False).round(2).reset_index()


def category_month_matrix(df):
    """Rows = category, columns = month, values = amount spent (for heatmaps)."""
    return expenses_only(df).pivot_table(index="category", columns="year_month",
                                         values="amount", aggfunc="sum", fill_value=0)


# ---------------------------------------------------------------------------
# Budget tracking
# ---------------------------------------------------------------------------
def budget_status(utilisation_pct):
    """Classify how much of the budget has been used."""
    if utilisation_pct > config.BUDGET_EXCEEDED_PCT:
        return "Over Budget"
    if utilisation_pct >= config.BUDGET_WARNING_PCT:
        return "Near Limit"
    return "Within Budget"


def budget_vs_actual(df, budget):
    """
    Compare planned budget with actual spending for every month + category.
    variance > 0 means money was SAVED; variance < 0 means OVERSPENT.
    """
    actual = (expenses_only(df).groupby(["year_month", "category"])["amount"]
              .sum().rename("actual_spent").reset_index())
    # Only keep budget rows for months present in the (possibly filtered) data
    budget = budget[budget["month"].isin(df["year_month"].unique())]
    merged = budget.merge(actual, left_on=["month", "category"],
                          right_on=["year_month", "category"], how="left")
    merged = merged.drop(columns="year_month")
    merged["actual_spent"] = merged["actual_spent"].fillna(0)
    merged["variance"] = merged["budget_amount"] - merged["actual_spent"]
    merged["utilisation_pct"] = (merged["actual_spent"] / merged["budget_amount"] * 100).round(1)
    merged["status"] = merged["utilisation_pct"].apply(budget_status)
    return merged.round(2)


def budget_category_overview(bva):
    """Roll the month-by-month budget table up to one row per category."""
    overview = bva.groupby("category").agg(
        total_budget=("budget_amount", "sum"),
        total_actual=("actual_spent", "sum"),
        months_over_budget=("status", lambda s: (s == "Over Budget").sum()),
        months_tracked=("status", "count"),
    )
    overview["variance"] = overview["total_budget"] - overview["total_actual"]
    overview["utilisation_pct"] = (overview["total_actual"] / overview["total_budget"] * 100).round(1)
    overview["status"] = overview["utilisation_pct"].apply(budget_status)
    return overview.sort_values("utilisation_pct", ascending=False).round(2).reset_index()


def budget_alerts(bva, month):
    """Return the categories that are over budget or close to it for one month."""
    # Fixed bills paid exactly as planned (e.g. rent) are not worth an alert
    rows = bva[(bva["month"] == month) & (bva["status"] != "Within Budget")
               & (bva["actual_spent"] != bva["budget_amount"])]
    return rows.sort_values("utilisation_pct", ascending=False)


# ---------------------------------------------------------------------------
# Behaviour analysis
# ---------------------------------------------------------------------------
def payment_mode_summary(df):
    expenses = expenses_only(df)
    summary = expenses.groupby("payment_mode")["amount"].agg(total_spent="sum", num_transactions="count")
    summary["share_pct"] = summary["total_spent"] / summary["total_spent"].sum() * 100
    return summary.sort_values("total_spent", ascending=False).round(2).reset_index()


def weekday_summary(df):
    """Average spend per day for each weekday (Monday..Sunday)."""
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    # Exclude fixed bills (rent, EMIs) because their date is fixed, not a choice
    variable = expenses_only(df)[lambda d: d["cost_nature"] == "Variable"]
    daily = variable.groupby(["date", "day_of_week"])["amount"].sum().reset_index()
    summary = daily.groupby("day_of_week")["amount"].mean().reindex(order).fillna(0)
    return summary.round(2).rename("avg_daily_spend").reset_index()


def top_merchants(df, n=10):
    expenses = expenses_only(df)
    return (expenses.groupby(["merchant", "category"])["amount"]
            .agg(total_spent="sum", num_transactions="count")
            .sort_values("total_spent", ascending=False).head(n).round(2).reset_index())


def needs_wants_savings(df):
    """
    50/30/20 rule (popular personal-finance guideline):
        50% of income -> Needs (essential), 30% -> Wants, 20% -> Savings.
    Returns actual % for each bucket next to the recommended %.
    """
    income = income_only(df)["amount"].sum()
    expenses = expenses_only(df)
    needs = expenses[expenses["expense_type"] == "Essential"]["amount"].sum()
    wants = expenses[expenses["expense_type"] == "Discretionary"]["amount"].sum()
    savings = income - needs - wants
    if income == 0:
        return pd.DataFrame(columns=["bucket", "amount", "actual_pct", "recommended_pct"])
    return pd.DataFrame({
        "bucket": ["Needs", "Wants", "Savings"],
        "amount": [needs, wants, savings],
        "actual_pct": [needs / income * 100, wants / income * 100, savings / income * 100],
        "recommended_pct": [50, 30, 20],
    }).round(1)


def year_over_year(df):
    """Compare each category's spend between years."""
    table = expenses_only(df).pivot_table(index="category", columns="year", values="amount",
                                          aggfunc="sum", fill_value=0)
    years = sorted(table.columns)
    if len(years) >= 2:
        prev, curr = years[-2], years[-1]
        table["change_pct"] = ((table[curr] - table[prev]) / table[prev].where(table[prev] > 0) * 100).round(1)
    table.columns = [str(c) for c in table.columns]
    return table.round(2).reset_index()


# ---------------------------------------------------------------------------
# Automatic insights (plain-English findings)
# ---------------------------------------------------------------------------
def fmt_money(x):
    """Format money the Indian way for text: ₹1,250 and -₹500 (not ₹-500)."""
    sign = "-" if x < 0 else ""
    return f"{sign}{config.CURRENCY}{abs(x):,.0f}"


def generate_insights(df, budget):
    """Turn the numbers into short written insights + recommendations."""
    rs = config.CURRENCY
    insights = []
    k = kpi_summary(df)
    monthly = monthly_summary(df)
    cats = category_summary(df)
    bva = budget_vs_actual(df, budget)
    overview = budget_category_overview(bva)
    nws = needs_wants_savings(df).set_index("bucket")
    pay = payment_mode_summary(df)

    insights.append(f"Over {k['months_covered']} months the user earned {rs}{k['total_income']:,.0f} and spent "
                    f"{rs}{k['total_expense']:,.0f}, saving {rs}{k['net_savings']:,.0f} "
                    f"(savings rate {k['savings_rate_pct']}%).")

    top3 = cats.head(3)
    insights.append("Top 3 spending categories: " + ", ".join(
        f"{r.category} ({r.share_pct:.1f}%)" for r in top3.itertuples()) +
        f" - together {top3['share_pct'].sum():.1f}% of all spending.")

    worst = monthly.loc[monthly["savings"].idxmin()]
    best = monthly.loc[monthly["savings"].idxmax()]
    insights.append(f"Best month: {best.year_month} (saved {rs}{best.savings:,.0f}). "
                    f"Worst month: {worst.year_month} (net {fmt_money(worst.savings)}).")

    negative = monthly[monthly["savings"] < 0]["year_month"].tolist()
    if negative:
        insights.append(f"Spending exceeded income in {len(negative)} month(s): {', '.join(negative)}.")

    over = overview[overview["months_over_budget"] > 0].head(3)
    for r in over.itertuples():
        insights.append(f"{r.category} went over budget in {r.months_over_budget} of {r.months_tracked} months "
                        f"(overall {r.utilisation_pct}% of budget used).")

    if "Savings" in nws.index:
        s = nws.loc["Savings", "actual_pct"]
        w = nws.loc["Wants", "actual_pct"]
        verdict = "meets" if s >= 20 else "is below"
        insights.append(f"50/30/20 check: savings are {s}% of income, which {verdict} the 20% target; "
                        f"wants take {w}% (target 30%).")

    digital = pay[pay["payment_mode"].isin(["UPI", "Debit Card", "Credit Card", "Net Banking"])]["share_pct"].sum()
    insights.append(f"{digital:.1f}% of spending is digital; UPI alone is "
                    f"{pay.set_index('payment_mode').get('share_pct', pd.Series()).get('UPI', 0):.1f}%.")

    # Festive season effect (Oct-Nov vs other months)
    exp = expenses_only(df)
    shopping = exp[exp["category"] == "Shopping"].groupby("month")["amount"].sum()
    if {10, 11}.issubset(shopping.index) and len(shopping) > 2:
        festive = shopping.loc[[10, 11]].mean()
        normal = shopping.drop([10, 11]).mean()
        insights.append(f"Festive effect: Shopping in Oct-Nov is {festive / normal:.1f}x a normal month "
                        f"- plan a dedicated Diwali fund.")

    # Recommendations
    recs = []
    for r in over.itertuples():
        avg_over = -bva[(bva["category"] == r.category) & (bva["variance"] < 0)]["variance"].mean()
        recs.append(f"Review the {r.category} budget: when it is exceeded, overspend averages {rs}{avg_over:,.0f}.")
    if "Food & Dining" in cats["category"].values:
        fd = cats.set_index("category").loc["Food & Dining", "avg_per_month"]
        recs.append(f"Cutting food-delivery spend by 20% would save about {rs}{fd * 0.2 * 12:,.0f} per year.")
    recs.append("Automate a fixed SIP/RD transfer on salary day so the 20% savings target is met first.")
    return insights, recs


def main():
    df, budget = load_transactions(), load_budget()
    rs = config.CURRENCY
    print("=" * 60)
    print("PERSONAL EXPENSE TRACKER - ANALYSIS SUMMARY")
    print("=" * 60)
    for key, value in kpi_summary(df).items():
        if isinstance(value, float):
            value = f"{value:,.2f}"
        print(f"{key:<25}: {value}")
    print("\nCategory summary:\n", category_summary(df).to_string(index=False))
    print("\nBudget overview:\n", budget_category_overview(budget_vs_actual(df, budget)).to_string(index=False))
    print("\n50/30/20:\n", needs_wants_savings(df).to_string(index=False))
    insights, recs = generate_insights(df, budget)
    print("\nINSIGHTS")
    for i, line in enumerate(insights, 1):
        print(f" {i}. {line}")
    print("\nRECOMMENDATIONS")
    for i, line in enumerate(recs, 1):
        print(f" {i}. {line}")
    print(f"\n(All amounts in {rs})")


if __name__ == "__main__":
    main()
