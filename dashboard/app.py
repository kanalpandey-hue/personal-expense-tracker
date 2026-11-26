"""
app.py - Interactive Personal Expense Tracker & Budget Dashboard
================================================================
Built with Streamlit (turns a Python script into a web app) and Plotly
(interactive charts with hover tooltips and zoom).

Run from the project folder:
    streamlit run dashboard/app.py

Pages (tabs):
    1. Overview        - KPIs, income vs expense, savings trend
    2. Categories      - where the money goes
    3. Budget Tracker  - budget vs actual, alerts for any month
    4. Insights        - automatic findings + what-if savings simulator
    5. Transactions    - searchable table + CSV download
    6. Add Expense     - log a new expense (saved to data/user_entries.csv)
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Let this file import our modules from the "src" folder
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
import analysis  # noqa: E402
import config  # noqa: E402
from data_cleaning import add_features  # noqa: E402

RS = config.CURRENCY
BLUE, ORANGE, RED, GREEN, AMBER, VIOLET = "#2a78d6", "#eb6834", "#d03b3b", "#0ca30c", "#fab219", "#6250d6"
STATUS_COLORS = {"Within Budget": GREEN, "Near Limit": AMBER, "Over Budget": RED}
STATUS_ICON = {"Within Budget": "✅", "Near Limit": "⚠️", "Over Budget": "🔴"}

st.set_page_config(page_title="Expense Tracker & Budget Dashboard", page_icon="💰", layout="wide")


# ---------------------------------------------------------------------------
# Data loading (cached so the app stays fast)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = analysis.load_transactions()
    # Add any expenses the user entered through the "Add Expense" tab
    if config.USER_ENTRIES_FILE.exists():
        user = pd.read_csv(config.USER_ENTRIES_FILE)
        if not user.empty:
            user["is_large_spend"] = False
            df = pd.concat([df, add_features(user)], ignore_index=True)
    return df, analysis.load_budget()


def money(x):
    """Format 1234.5 as ₹1,235 and -500 as -₹500."""
    sign = "-" if x < 0 else ""
    return f"{sign}{RS}{abs(x):,.0f}"


def style_fig(fig, height=380):
    """Common clean look for every Plotly chart."""
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified",
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"))
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)", zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


df_all, budget = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.title("💰 Filters")
months = sorted(df_all["year_month"].unique())
start_m, end_m = st.sidebar.select_slider("Period", options=months, value=(months[0], months[-1]))

expense_cats = sorted(df_all.loc[df_all["txn_type"] == "Debit", "category"].unique())
chosen_cats = st.sidebar.multiselect("Expense categories", expense_cats, default=expense_cats)
modes = sorted(df_all["payment_mode"].unique())
chosen_modes = st.sidebar.multiselect("Payment modes", modes, default=modes)

# Filter rules: income rows are always kept (so savings stay correct);
# category / payment filters apply to expenses only.
in_period = df_all["year_month"].between(start_m, end_m)
is_income = df_all["txn_type"] == "Credit"
expense_ok = df_all["category"].isin(chosen_cats) & df_all["payment_mode"].isin(chosen_modes)
df = df_all[in_period & (is_income | expense_ok)]
budget_f = budget[budget["category"].isin(chosen_cats)]

st.sidebar.caption(f"{len(df):,} transactions selected")
st.sidebar.markdown("---")
st.sidebar.caption("HCL Tech Data Analytics Project\nDomain: Banking & Finance")

if df.empty or analysis.expenses_only(df).empty:
    st.warning("No expense data for the selected filters. Please widen your selection.")
    st.stop()

# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------
st.title("Personal Expense Tracker & Budget Dashboard")
st.caption(f"Period: **{start_m}** to **{end_m}**  ·  all amounts in Indian Rupees ({RS})")

if len(chosen_cats) < len(expense_cats) or len(chosen_modes) < len(modes):
    st.info("Filters are active: expense and savings figures include only the selected "
            "categories / payment modes (income is always included).")

k = analysis.kpi_summary(df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Income", money(k["total_income"]))
c2.metric("Total Expense", money(k["total_expense"]))
c3.metric("Net Savings", money(k["net_savings"]))
c4.metric("Savings Rate", f"{k['savings_rate_pct']}%",
          delta=f"{k['savings_rate_pct'] - 20:+.1f} pts vs 20% goal")
c5.metric("Avg Monthly Spend", money(k["avg_monthly_expense"]))

tabs = st.tabs(["📊 Overview", "🗂️ Categories", "🎯 Budget Tracker", "💡 Insights",
                "📄 Transactions", "➕ Add Expense"])

monthly = analysis.monthly_summary(df)

# ---------------------------------------------------------------------------
# 1. Overview
# ---------------------------------------------------------------------------
with tabs[0]:
    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        fig.add_bar(x=monthly["year_month"], y=monthly["income"], name="Income", marker_color=BLUE)
        fig.add_bar(x=monthly["year_month"], y=monthly["expense"], name="Expense", marker_color=ORANGE)
        fig.update_layout(title="Monthly income vs expense", barmode="group")
        st.plotly_chart(style_fig(fig), width="stretch")
    with right:
        colors = [BLUE if s >= 0 else RED for s in monthly["savings"]]
        fig = go.Figure(go.Bar(x=monthly["year_month"], y=monthly["savings"], marker_color=colors,
                               name="Net savings"))
        fig.update_layout(title="Net savings per month (red = deficit)")
        st.plotly_chart(style_fig(fig), width="stretch")

    left, right = st.columns([3, 2])
    with left:
        fig = px.area(monthly, x="year_month", y="cumulative_savings", title="Cumulative savings")
        fig.update_traces(line_color=BLUE, fillcolor="rgba(42,120,214,0.12)")
        st.plotly_chart(style_fig(fig, 320), width="stretch")
    with right:
        nws = analysis.needs_wants_savings(df)
        fig = go.Figure()
        fig.add_bar(y=nws["bucket"], x=nws["actual_pct"], orientation="h", name="Actual", marker_color=BLUE,
                    text=[f"{v:.1f}%" for v in nws["actual_pct"]], textposition="outside")
        fig.add_bar(y=nws["bucket"], x=nws["recommended_pct"], orientation="h", name="Recommended",
                    marker_color="#c3c2b7")
        fig.update_layout(title="50/30/20 rule (% of income)", barmode="group", hovermode="y unified")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style_fig(fig, 320), width="stretch")

# ---------------------------------------------------------------------------
# 2. Categories
# ---------------------------------------------------------------------------
with tabs[1]:
    cats = analysis.category_summary(df)
    left, right = st.columns(2)
    with left:
        fig = px.bar(cats.sort_values("total_spent"), x="total_spent", y="category", orientation="h",
                     title="Total spend by category", text=cats.sort_values("total_spent")["share_pct"]
                     .map(lambda v: f"{v:.1f}%"), color_discrete_sequence=[BLUE])
        fig.update_layout(hovermode="y unified", xaxis_title=f"Total spent ({RS})", yaxis_title=None)
        st.plotly_chart(style_fig(fig, 450), width="stretch")
    with right:
        exp = analysis.expenses_only(df)
        trend = exp.groupby(["year_month", "expense_type"])["amount"].sum().reset_index()
        fig = px.line(trend, x="year_month", y="amount", color="expense_type", markers=True,
                      title="Needs vs wants over time",
                      color_discrete_map={"Essential": BLUE, "Discretionary": ORANGE})
        fig.update_layout(yaxis_title=f"Amount ({RS})", xaxis_title=None, legend_title=None)
        st.plotly_chart(style_fig(fig, 450), width="stretch")

    st.subheader("Category × month spending")
    matrix = analysis.category_month_matrix(df)
    fig = px.imshow(matrix, aspect="auto", color_continuous_scale="Blues",
                    labels=dict(color=f"Spent ({RS})", x="Month", y="Category"))
    st.plotly_chart(style_fig(fig, 420), width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Top merchants")
        st.dataframe(analysis.top_merchants(df, 10), hide_index=True, width="stretch",
                     column_config={"total_spent": st.column_config.NumberColumn(format=f"{RS}%.0f")})
    with right:
        pay = analysis.payment_mode_summary(df)
        fig = px.bar(pay.sort_values("share_pct"), x="share_pct", y="payment_mode", orientation="h",
                     title="Share of spending by payment mode", color_discrete_sequence=[BLUE],
                     text=pay.sort_values("share_pct")["share_pct"].map(lambda v: f"{v:.1f}%"))
        fig.update_layout(xaxis_title="% of spending", yaxis_title=None, hovermode="y unified")
        st.plotly_chart(style_fig(fig, 330), width="stretch")

# ---------------------------------------------------------------------------
# 3. Budget tracker
# ---------------------------------------------------------------------------
with tabs[2]:
    bva = analysis.budget_vs_actual(df, budget_f)
    if bva.empty:
        st.info("No budget defined for the selected period / categories.")
    else:
        budget_months = sorted(bva["month"].unique())
        month = st.selectbox("Choose a month to inspect", budget_months, index=len(budget_months) - 1)
        mb = bva[bva["month"] == month].sort_values("utilisation_pct", ascending=False)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Budget", money(mb["budget_amount"].sum()))
        m2.metric("Spent", money(mb["actual_spent"].sum()))
        m3.metric("Remaining", money(mb["variance"].sum()))
        m4.metric("Categories over budget", int((mb["status"] == "Over Budget").sum()))

        alerts = analysis.budget_alerts(bva, month)
        if alerts.empty:
            st.success("All categories are within budget this month. 🎉")
        for r in alerts.itertuples():
            msg = (f"{STATUS_ICON[r.status]} **{r.category}**: spent {money(r.actual_spent)} of "
                   f"{money(r.budget_amount)} ({r.utilisation_pct:.0f}%)")
            (st.error if r.status == "Over Budget" else st.warning)(msg)

        fig = go.Figure()
        fig.add_bar(y=mb["category"], x=mb["budget_amount"], orientation="h", name="Budget",
                    marker_color="#c3c2b7")
        fig.add_bar(y=mb["category"], x=mb["actual_spent"], orientation="h", name="Actual",
                    marker_color=[STATUS_COLORS[s] for s in mb["status"]])
        fig.update_layout(title=f"Budget vs actual - {month}", barmode="group", hovermode="y unified")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style_fig(fig, 480), width="stretch")

        st.subheader("Whole-period budget scorecard")
        overview = analysis.budget_category_overview(bva)
        overview.insert(0, "", overview["status"].map(STATUS_ICON))
        st.dataframe(overview, hide_index=True, width="stretch", column_config={
            "total_budget": st.column_config.NumberColumn(format=f"{RS}%.0f"),
            "total_actual": st.column_config.NumberColumn(format=f"{RS}%.0f"),
            "variance": st.column_config.NumberColumn(format=f"{RS}%.0f"),
            "utilisation_pct": st.column_config.ProgressColumn("utilisation %", format="%.0f%%",
                                                               min_value=0, max_value=150)})

        heat = bva.pivot(index="category", columns="month", values="utilisation_pct").clip(upper=200)
        fig = px.imshow(heat, aspect="auto", zmin=0, zmax=200,
                        color_continuous_scale=[[0, "#256abf"], [0.5, "#f0efec"], [1, "#b52a2a"]],
                        labels=dict(color="% used"), title="Budget utilisation heatmap (100% = on budget)")
        st.plotly_chart(style_fig(fig, 420), width="stretch")

# ---------------------------------------------------------------------------
# 4. Insights + what-if simulator
# ---------------------------------------------------------------------------
with tabs[3]:
    insights, recs = analysis.generate_insights(df, budget_f if not budget_f.empty else budget)
    left, right = st.columns(2)
    with left:
        st.subheader("Key insights")
        for line in insights:
            st.markdown(f"- {line}")
    with right:
        st.subheader("Recommendations")
        for line in recs:
            st.markdown(f"- {line}")

    st.markdown("---")
    st.subheader("🔮 What-if savings simulator")
    st.caption("Move the sliders to see how cutting discretionary spending changes yearly savings.")
    cats = analysis.category_summary(df).set_index("category")
    discretionary = [c for c in ["Shopping", "Food & Dining", "Entertainment", "Travel", "Subscriptions"]
                     if c in cats.index]
    cols = st.columns(len(discretionary) or 1)
    extra_per_month = 0.0
    for col, cat in zip(cols, discretionary):
        cut = col.slider(f"Cut {cat} by", 0, 50, 10, step=5, format="%d%%")
        extra_per_month += cats.loc[cat, "avg_per_month"] * cut / 100
    current_monthly_saving = k["avg_monthly_income"] - k["avg_monthly_expense"]
    new_rate = (current_monthly_saving + extra_per_month) / k["avg_monthly_income"] * 100 if k["avg_monthly_income"] else 0
    s1, s2, s3 = st.columns(3)
    s1.metric("Extra savings / month", money(extra_per_month))
    s2.metric("Extra savings / year", money(extra_per_month * 12))
    s3.metric("New savings rate", f"{new_rate:.1f}%", delta=f"{new_rate - k['savings_rate_pct']:+.1f} pts")

# ---------------------------------------------------------------------------
# 5. Transactions
# ---------------------------------------------------------------------------
with tabs[4]:
    search = st.text_input("Search description / merchant", placeholder="e.g. Swiggy")
    view = df.sort_values("date", ascending=False)
    if search:
        mask = (view["description"].str.contains(search, case=False, na=False)
                | view["merchant"].str.contains(search, case=False, na=False))
        view = view[mask]
    only_large = st.checkbox("Show only unusually large spends (IQR outliers)")
    if only_large:
        view = view[view["is_large_spend"] == True]  # noqa: E712
    cols = ["date", "transaction_id", "description", "category", "amount", "txn_type", "payment_mode", "merchant"]
    st.dataframe(view[cols], hide_index=True, width="stretch", height=450,
                 column_config={"date": st.column_config.DateColumn(format="DD MMM YYYY"),
                                "amount": st.column_config.NumberColumn(format=f"{RS}%.2f")})
    st.download_button("⬇️ Download filtered transactions (CSV)", view[cols].to_csv(index=False),
                       file_name="filtered_transactions.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# 6. Add expense
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Log a new transaction")
    if "saved_msg" in st.session_state:
        st.success(st.session_state.pop("saved_msg"))
    st.caption(f"Entries are saved to `{config.USER_ENTRIES_FILE.relative_to(config.PROJECT_ROOT)}` "
               "and immediately included in every chart.")
    with st.form("add_expense", clear_on_submit=True):
        a, b = st.columns(2)
        txn_type = a.radio("Type", ["Debit", "Credit"], horizontal=True,
                           format_func=lambda t: "Expense (Debit)" if t == "Debit" else "Income (Credit)")
        txn_date = b.date_input("Date", value=date.today())
        category = a.selectbox("Category", config.EXPENSE_CATEGORIES + config.INCOME_CATEGORIES)
        amount = b.number_input(f"Amount ({RS})", min_value=1.0, step=50.0)
        merchant = a.text_input("Merchant / payee")
        mode = b.selectbox("Payment mode", config.PAYMENT_MODES)
        note = st.text_input("Description (optional)")
        submitted = st.form_submit_button("Save transaction")

    if submitted:
        # Basic validation: expense categories must be Debit, income categories Credit
        if txn_type == "Debit" and category in config.INCOME_CATEGORIES:
            st.error("Please choose an expense category for a Debit.")
        elif txn_type == "Credit" and category in config.EXPENSE_CATEGORIES:
            st.error("Please choose an income category for a Credit.")
        elif not merchant.strip():
            st.error("Please enter a merchant / payee.")
        else:
            existing = (pd.read_csv(config.USER_ENTRIES_FILE)
                        if config.USER_ENTRIES_FILE.exists() else pd.DataFrame())
            new_row = pd.DataFrame([{
                "transaction_id": f"USR{len(existing) + 1:05d}",
                "date": txn_date.isoformat(),
                "description": note.strip() or f"Manual entry - {merchant.strip()}",
                "category": category, "amount": round(amount, 2), "txn_type": txn_type,
                "payment_mode": mode, "merchant": merchant.strip(),
            }])
            pd.concat([existing, new_row], ignore_index=True).to_csv(config.USER_ENTRIES_FILE, index=False)
            load_data.clear()   # clear the cache so the new entry shows up
            # Remember the message, because st.rerun() reloads the page
            st.session_state["saved_msg"] = f"Saved {txn_type.lower()} of {money(amount)} for {category}."
            st.rerun()

    if config.USER_ENTRIES_FILE.exists():
        st.markdown("**Your manual entries**")
        st.dataframe(pd.read_csv(config.USER_ENTRIES_FILE), hide_index=True, width="stretch")
