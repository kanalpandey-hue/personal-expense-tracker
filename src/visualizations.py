"""
visualizations.py
-----------------
Creates static, report-ready charts (PNG) with Matplotlib.
These images go into the project report / presentation.

Design choices (so charts are easy to read):
    * One clear message per chart, written in the title
    * Colour-blind-safe palette, colours used consistently
      (blue = income/savings, orange = expense, red = over budget)
    * Horizontal bars for category names (long labels stay readable)
    * No pie charts with 12 slices - bars compare sizes far better

Run:  python src/visualizations.py
"""

import matplotlib

matplotlib.use("Agg")  # draw to files only (no pop-up windows)

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

import analysis
import config

# ---------------------------------------------------------------------------
# Colour palette (validated for colour-blind readers)
# ---------------------------------------------------------------------------
BLUE = "#2a78d6"     # income / savings / neutral data
ORANGE = "#eb6834"   # expenses
AQUA = "#1baf7a"
VIOLET = "#6250d6"
GOOD = "#0ca30c"     # within budget
WARN = "#fab219"     # near limit
BAD = "#d03b3b"      # over budget
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

STATUS_COLORS = {"Within Budget": GOOD, "Near Limit": WARN, "Over Budget": BAD}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 10,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 24,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.axisbelow": True, "legend.frameon": False,
})


def rupees(x, _pos=None):
    """Format axis numbers as ₹12k / ₹1.2L (Indian style)."""
    if abs(x) >= 100000:
        return f"₹{x / 100000:.1f}L"
    if abs(x) >= 1000:
        return f"₹{x / 1000:.0f}k"
    return f"₹{x:.0f}"


def subtitle(ax, text):
    """Small grey line under the title explaining how to read the chart."""
    ax.text(0, 1.01, text, transform=ax.transAxes, fontsize=9, color=MUTED, va="bottom")


def save(fig, name):
    path = config.FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("  saved", path.name)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def chart_income_vs_expense(monthly):
    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(monthly))
    w = 0.4
    ax.bar([i - w / 2 for i in x], monthly["income"], width=w, color=BLUE, label="Income")
    ax.bar([i + w / 2 for i in x], monthly["expense"], width=w, color=ORANGE, label="Expense")
    ax.set_xticks(list(x), monthly["year_month"], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(rupees))
    ax.grid(axis="x", visible=False)
    ax.set_title("Monthly income vs expense")
    subtitle(ax, "Months where the orange bar is taller than the blue bar = spent more than earned")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=2)
    save(fig, "01_income_vs_expense.png")


def chart_net_savings(monthly):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    colors = [BLUE if s >= 0 else BAD for s in monthly["savings"]]
    ax.bar(monthly["year_month"], monthly["savings"], color=colors)
    ax.axhline(0, color=INK_2, linewidth=1)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(rupees))
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="x", visible=False)
    # Label only the deficit months (selective labels avoid clutter)
    for m, s in zip(monthly["year_month"], monthly["savings"]):
        if s < 0:
            ax.annotate(rupees(s), (m, s), xytext=(0, -12), textcoords="offset points",
                        ha="center", fontsize=8, color=INK)
    ax.set_title("Net savings per month")
    subtitle(ax, "Blue = money saved, red = deficit month (spending exceeded income)")
    save(fig, "02_net_savings.png")


def chart_cumulative_savings(monthly):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(monthly["year_month"], monthly["cumulative_savings"], color=BLUE, linewidth=2,
            marker="o", markersize=5)
    ax.fill_between(monthly["year_month"], monthly["cumulative_savings"], color=BLUE, alpha=0.08)
    last = monthly.iloc[-1]
    ax.annotate(f"{rupees(last.cumulative_savings)} saved", (last.year_month, last.cumulative_savings),
                xytext=(-10, 10), textcoords="offset points", ha="right", fontsize=10,
                color=INK, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(rupees))
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Cumulative savings growth")
    subtitle(ax, "Running total of (income - expense) since January 2024")
    save(fig, "03_cumulative_savings.png")


def chart_category_spend(cats):
    cats = cats.sort_values("avg_per_month")
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(cats["category"], cats["avg_per_month"], color=BLUE, height=0.65)
    for bar, share in zip(bars, cats["share_pct"]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  {rupees(bar.get_width())}  ({share:.1f}%)", va="center", fontsize=9, color=INK_2)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(rupees))
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, cats["avg_per_month"].max() * 1.25)
    ax.set_title("Average monthly spend by category")
    subtitle(ax, "Label = average per month (share of total spending)")
    save(fig, "04_category_spend.png")


def chart_budget_utilisation(overview):
    data = overview.sort_values("utilisation_pct")
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [STATUS_COLORS[s] for s in data["status"]]
    bars = ax.barh(data["category"], data["utilisation_pct"], color=colors, height=0.65)
    ax.axvline(100, color=INK, linestyle="--", linewidth=1)
    ax.text(100, len(data) - 0.4, " 100% = budget", fontsize=9, color=INK_2, va="bottom")
    for bar, status in zip(bars, data["status"]):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{bar.get_width():.0f}%  {status}", va="center", fontsize=9, color=INK_2,
                bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1))
    ax.set_xlim(0, max(140, data["utilisation_pct"].max() + 30))
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.grid(axis="y", visible=False)
    ax.set_title("Budget utilisation by category (24 months)")
    subtitle(ax, "Actual spend as % of planned budget. Green < 80%, amber 80-100%, red > 100%")
    save(fig, "05_budget_utilisation.png")


def chart_budget_heatmap(bva):
    matrix = bva.pivot(index="category", columns="month", values="utilisation_pct")
    matrix = matrix.loc[matrix.mean(axis=1).sort_values(ascending=False).index]
    # Diverging colours: blue = under budget, grey = on budget, red = over budget
    cmap = LinearSegmentedColormap.from_list("budget", ["#256abf", "#86b6ef", "#f0efec", "#f19a8f", "#b52a2a"])
    norm = TwoSlopeNorm(vmin=0, vcenter=100, vmax=200)
    fig, ax = plt.subplots(figsize=(14, 6))
    # pcolormesh with a white edge gives a small gap between cells (easier to read)
    im = ax.pcolormesh(matrix.clip(upper=200), cmap=cmap, norm=norm, edgecolors=SURFACE, linewidth=1.5)
    ax.invert_yaxis()
    ax.set_yticks([i + 0.5 for i in range(len(matrix))], matrix.index)
    ax.set_xticks([i + 0.5 for i in range(len(matrix.columns))], matrix.columns,
                  rotation=60, ha="right", fontsize=8)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cbar.set_label("% of budget used (capped at 200%)")
    cbar.outline.set_visible(False)
    ax.set_title("Budget heatmap: every category, every month")
    subtitle(ax, "Red cells = overspent that month, blue = under budget, grey = on target")
    save(fig, "06_budget_heatmap.png")


def chart_payment_modes(pay):
    pay = pay.sort_values("total_spent")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.barh(pay["payment_mode"], pay["share_pct"], color=BLUE, height=0.6)
    for bar, n in zip(bars, pay["num_transactions"]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{bar.get_width():.1f}%  ({n} txns)", va="center", fontsize=9, color=INK_2)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_xlim(0, pay["share_pct"].max() * 1.3)
    ax.grid(axis="y", visible=False)
    ax.set_title("Share of spending by payment mode")
    subtitle(ax, "UPI dominates everyday payments; Net Banking carries large fixed bills like rent")
    save(fig, "07_payment_modes.png")


def chart_weekday(weekday):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = [VIOLET if d in ("Saturday", "Sunday") else BLUE for d in weekday["day_of_week"]]
    ax.bar(weekday["day_of_week"].str[:3], weekday["avg_daily_spend"], color=colors, width=0.6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(rupees))
    ax.grid(axis="x", visible=False)
    ax.set_title("Average variable spend per day of week")
    subtitle(ax, "Violet = weekend. Fixed bills (rent, EMIs) excluded")
    save(fig, "08_weekday_spend.png")


def chart_50_30_20(nws):
    fig, ax = plt.subplots(figsize=(9, 4))
    y = range(len(nws))
    h = 0.36
    ax.barh([i + h / 2 for i in y], nws["actual_pct"], height=h, color=BLUE, label="Actual")
    ax.barh([i - h / 2 for i in y], nws["recommended_pct"], height=h, color="#c3c2b7", label="Recommended")
    for i, (a, r) in enumerate(zip(nws["actual_pct"], nws["recommended_pct"])):
        ax.text(a + 0.8, i + h / 2, f"{a:.1f}%", va="center", fontsize=9, color=INK)
        ax.text(r + 0.8, i - h / 2, f"{r}%", va="center", fontsize=9, color=MUTED)
    ax.set_yticks(list(y), nws["bucket"])
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_xlim(0, 65)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    ax.set_title("50/30/20 rule: needs, wants and savings")
    subtitle(ax, "Share of total income. Recommended: 50% needs, 30% wants, 20% savings")
    save(fig, "09_50_30_20_rule.png")


def chart_essential_vs_discretionary(df):
    exp = analysis.expenses_only(df)
    trend = exp.pivot_table(index="year_month", columns="expense_type", values="amount", aggfunc="sum")
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(trend.index, trend["Essential"], color=BLUE, linewidth=2, marker="o", markersize=4, label="Essential (needs)")
    ax.plot(trend.index, trend["Discretionary"], color=ORANGE, linewidth=2, marker="o", markersize=4,
            label="Discretionary (wants)")
    for col, color in (("Essential", BLUE), ("Discretionary", ORANGE)):
        ax.annotate(col, (trend.index[-1], trend[col].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK_2)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(rupees))
    ax.tick_params(axis="x", rotation=45)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.2), ncol=2)
    ax.set_title("Needs vs wants over time")
    subtitle(ax, "Spikes in wants line up with festive (Oct-Nov) and holiday months")
    save(fig, "10_needs_vs_wants_trend.png")


def main():
    config.ensure_folders()
    df, budget = analysis.load_transactions(), analysis.load_budget()
    monthly = analysis.monthly_summary(df)
    bva = analysis.budget_vs_actual(df, budget)
    print("Creating charts...")
    chart_income_vs_expense(monthly)
    chart_net_savings(monthly)
    chart_cumulative_savings(monthly)
    chart_category_spend(analysis.category_summary(df))
    chart_budget_utilisation(analysis.budget_category_overview(bva))
    chart_budget_heatmap(bva)
    chart_payment_modes(analysis.payment_mode_summary(df))
    chart_weekday(analysis.weekday_summary(df))
    chart_50_30_20(analysis.needs_wants_savings(df))
    chart_essential_vs_discretionary(df)
    print(f"All charts saved in {config.FIGURES_DIR}")


if __name__ == "__main__":
    main()
