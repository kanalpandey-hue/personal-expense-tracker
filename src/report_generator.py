"""
report_generator.py
-------------------
Builds the two written deliverables:

    1. reports/Expense_Analysis_Report.xlsx
         A formatted Excel workbook (many managers & banks still live in Excel):
         - Summary sheet with KPIs, insights and native Excel charts
         - Monthly, category, budget, payment and merchant analysis sheets
         - Conditional colours on budget status (green / amber / red)
         - Clean transaction data + data dictionary

    2. reports/insights_summary.md
         A plain-English findings report with the charts embedded.

Run:  python src/report_generator.py
"""

from datetime import datetime

import pandas as pd
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import analysis
import config

HEADER_FILL = PatternFill("solid", fgColor="1F3864")   # dark navy (banking style)
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=16, color="1F3864")
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
RUPEE_FMT = '"₹"#,##0'
PCT_FMT = '0.0"%"'

DATA_DICTIONARY = [
    ("transaction_id", "Unique ID of the transaction (TXN000001...)"),
    ("date", "Transaction date (YYYY-MM-DD)"),
    ("description", "Narration as shown on the bank statement"),
    ("category", "Spending / income category (12 expense + 4 income categories)"),
    ("amount", "Transaction amount in ₹ (always positive)"),
    ("txn_type", "Debit = money out, Credit = money in"),
    ("payment_mode", "UPI, Debit Card, Credit Card, Net Banking, Cash or Unknown"),
    ("merchant", "Who was paid / who paid"),
    ("is_large_spend", "True if amount is unusually high for its category (IQR rule)"),
    ("year, month, month_name, year_month, quarter", "Date parts used for grouping"),
    ("day_of_week, is_weekend", "Weekday name and weekend flag"),
    ("signed_amount", "+amount for credits, -amount for debits (cash-flow maths)"),
    ("expense_type", "Income / Essential (needs) / Discretionary (wants)"),
    ("cost_nature", "Income / Fixed (same every month) / Variable"),
]


# ---------------------------------------------------------------------------
# Excel helpers
# ---------------------------------------------------------------------------
def style_table(ws, df, start_row=1, money_cols=(), pct_cols=()):
    """Apply header colours, borders, number formats and column widths."""
    for col_idx, col_name in enumerate(df.columns, start=1):
        cell = ws.cell(row=start_row, column=col_idx)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        fmt = RUPEE_FMT if col_name in money_cols else PCT_FMT if col_name in pct_cols else None
        for row in range(start_row + 1, start_row + len(df) + 1):
            c = ws.cell(row=row, column=col_idx)
            c.border = BORDER
            if fmt:
                c.number_format = fmt
        # Column width = longest value (capped) so text is readable
        longest = max([len(str(col_name))] + [len(str(v)) for v in df[col_name].head(200)])
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(12, longest + 3), 45)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)  # keep header visible while scrolling
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(df.columns))}{start_row + len(df)}"


def add_status_colours(ws, column_letter, first_row, last_row):
    """Green / amber / red fill depending on the budget status text."""
    rng = f"{column_letter}{first_row}:{column_letter}{last_row}"
    rules = [("Over Budget", "F8CBAD", "9C0006"), ("Near Limit", "FFE699", "7F6000"),
             ("Within Budget", "C6EFCE", "006100")]
    for text, fill, font in rules:
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{text}"'],
                                                      fill=PatternFill("solid", fgColor=fill),
                                                      font=Font(color=font)))


def write_sheet(writer, df, name, money_cols=(), pct_cols=(), status_col=None):
    df.to_excel(writer, sheet_name=name, index=False)
    ws = writer.sheets[name]
    style_table(ws, df, money_cols=money_cols, pct_cols=pct_cols)
    if status_col:
        letter = get_column_letter(df.columns.get_loc(status_col) + 1)
        add_status_colours(ws, letter, 2, len(df) + 1)
    return ws


def build_summary_sheet(wb, kpis, insights, recs, monthly_ws, n_months, cat_ws, n_cats):
    ws = wb.create_sheet("Summary", 0)   # index 0 = first tab
    ws["A1"] = "Personal Expense Tracker & Budget Dashboard"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"Analysis period: {n_months} months  |  Generated {datetime.now():%d %b %Y}"
    ws["A2"].font = Font(italic=True, color="595959")

    rows = [
        ("Total Income", kpis["total_income"], RUPEE_FMT),
        ("Total Expense", kpis["total_expense"], RUPEE_FMT),
        ("Net Savings", kpis["net_savings"], RUPEE_FMT),
        ("Savings Rate", kpis["savings_rate_pct"], PCT_FMT),
        ("Avg Monthly Income", kpis["avg_monthly_income"], RUPEE_FMT),
        ("Avg Monthly Expense", kpis["avg_monthly_expense"], RUPEE_FMT),
        ("Expense Transactions", kpis["num_expense_txns"], "#,##0"),
        ("Avg Transaction Value", kpis["avg_transaction_value"], RUPEE_FMT),
        ("Top Spending Category", kpis["top_spending_category"], None),
    ]
    ws["A4"], ws["B4"] = "Key Metric", "Value"
    for c in (ws["A4"], ws["B4"]):
        c.fill, c.font = HEADER_FILL, HEADER_FONT
    for i, (label, value, fmt) in enumerate(rows, start=5):
        ws.cell(row=i, column=1, value=label).border = BORDER
        cell = ws.cell(row=i, column=2, value=value)
        cell.border = BORDER
        cell.font = Font(bold=True)
        if fmt:
            cell.number_format = fmt
    ws.cell(row=5 + len(rows) + 1, column=1, value="See Key Insights & Recommendations from row 60 ↓").font = Font(italic=True, color="595959")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 20

    # Insights go BELOW the charts (row 60) so long sentences are not hidden behind them
    r = 60
    ws.cell(row=r, column=1, value="Key Insights").font = Font(bold=True, size=13, color="1F3864")
    for i, text in enumerate(insights, start=1):
        ws.cell(row=r + i, column=1, value=f"{i}. {text}")
    r += len(insights) + 2
    ws.cell(row=r, column=1, value="Recommendations").font = Font(bold=True, size=13, color="1F3864")
    for i, text in enumerate(recs, start=1):
        ws.cell(row=r + i, column=1, value=f"{i}. {text}")

    # --- Native Excel charts (they stay editable inside Excel) ---
    bar = BarChart()
    bar.title = "Monthly Income vs Expense"
    bar.y_axis.title = "₹"
    bar.height, bar.width = 8, 22
    data = Reference(monthly_ws, min_col=2, max_col=3, min_row=1, max_row=n_months + 1)
    cats = Reference(monthly_ws, min_col=1, min_row=2, max_row=n_months + 1)
    bar.add_data(data, titles_from_data=True)
    bar.set_categories(cats)
    bar.series[0].graphicalProperties.solidFill = "2A78D6"
    bar.series[1].graphicalProperties.solidFill = "EB6834"
    ws.add_chart(bar, "D4")

    line = LineChart()
    line.title = "Cumulative Savings"
    line.height, line.width = 8, 22
    # find the "cumulative_savings" column by its header name (safer than a hard-coded number)
    headers = [c.value for c in monthly_ws[1]]
    cum_col = headers.index("cumulative_savings") + 1
    line.add_data(Reference(monthly_ws, min_col=cum_col, min_row=1, max_row=n_months + 1), titles_from_data=True)
    line.set_categories(cats)
    line.series[0].graphicalProperties.line.solidFill = "2A78D6"
    ws.add_chart(line, "D21")

    cbar = BarChart()
    cbar.type = "bar"   # horizontal
    cbar.title = "Total Spend by Category"
    cbar.height, cbar.width = 10, 22
    cbar.add_data(Reference(cat_ws, min_col=2, min_row=1, max_row=n_cats + 1), titles_from_data=True)
    cbar.set_categories(Reference(cat_ws, min_col=1, min_row=2, max_row=n_cats + 1))
    cbar.series[0].graphicalProperties.solidFill = "2A78D6"
    cbar.legend = None
    ws.add_chart(cbar, "D38")


def build_excel_report(df, budget):
    monthly = analysis.monthly_summary(df)
    cats = analysis.category_summary(df)
    bva = analysis.budget_vs_actual(df, budget)
    overview = analysis.budget_category_overview(bva)
    insights, recs = analysis.generate_insights(df, budget)

    with pd.ExcelWriter(config.EXCEL_REPORT_FILE, engine="openpyxl") as writer:
        monthly_ws = write_sheet(writer, monthly, "Monthly Summary",
                                 money_cols=("income", "expense", "savings", "cumulative_savings"),
                                 pct_cols=("savings_rate_pct", "expense_mom_change_pct"))
        cat_ws = write_sheet(writer, cats, "Category Analysis",
                             money_cols=("total_spent", "avg_transaction", "avg_per_month"),
                             pct_cols=("share_pct",))
        write_sheet(writer, overview, "Budget Overview",
                    money_cols=("total_budget", "total_actual", "variance"),
                    pct_cols=("utilisation_pct",), status_col="status")
        write_sheet(writer, bva, "Budget vs Actual (Monthly)",
                    money_cols=("budget_amount", "actual_spent", "variance"),
                    pct_cols=("utilisation_pct",), status_col="status")
        write_sheet(writer, analysis.needs_wants_savings(df), "50-30-20 Rule",
                    money_cols=("amount",), pct_cols=("actual_pct", "recommended_pct"))
        write_sheet(writer, analysis.payment_mode_summary(df), "Payment Modes",
                    money_cols=("total_spent",), pct_cols=("share_pct",))
        write_sheet(writer, analysis.top_merchants(df, 15), "Top Merchants", money_cols=("total_spent",))
        write_sheet(writer, analysis.year_over_year(df), "Year over Year",
                    money_cols=("2024", "2025"), pct_cols=("change_pct",))
        txns = df.copy()
        txns["date"] = txns["date"].dt.date
        write_sheet(writer, txns, "Transactions (Clean)", money_cols=("amount", "signed_amount"))
        write_sheet(writer, pd.DataFrame(DATA_DICTIONARY, columns=["column", "meaning"]), "Data Dictionary")

        build_summary_sheet(writer.book, analysis.kpi_summary(df), insights, recs,
                            monthly_ws, len(monthly), cat_ws, len(cats))
    print(f"Excel report saved -> {config.EXCEL_REPORT_FILE}")


def build_markdown_report(df, budget):
    rs = config.CURRENCY
    k = analysis.kpi_summary(df)
    insights, recs = analysis.generate_insights(df, budget)
    overview = analysis.budget_category_overview(analysis.budget_vs_actual(df, budget))
    cats = analysis.category_summary(df)
    cleaning_log = config.CLEANING_LOG_FILE.read_text(encoding="utf-8").splitlines()[2:]

    def md_table(frame, cols, money=(), pct=()):
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for _, r in frame[cols].iterrows():
            cells = []
            for c in cols:
                v = r[c]
                if c in money:
                    v = f"{rs}{v:,.0f}"
                elif c in pct:
                    v = f"{v:.1f}%"
                cells.append(str(v))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    text = f"""# Personal Expense Tracker & Budget Dashboard: Insights Report

*Generated automatically on {datetime.now():%d %B %Y} by `src/report_generator.py`*

## 1. Headline numbers ({k['months_covered']} months)

| Metric | Value |
|---|---|
| Total income | {rs}{k['total_income']:,.0f} |
| Total expense | {rs}{k['total_expense']:,.0f} |
| Net savings | {rs}{k['net_savings']:,.0f} |
| Savings rate | {k['savings_rate_pct']}% |
| Average monthly expense | {rs}{k['avg_monthly_expense']:,.0f} |
| Expense transactions | {k['num_expense_txns']:,} |
| Top spending category | {k['top_spending_category']} |

## 2. Key insights

""" + "\n".join(f"{i}. {t}" for i, t in enumerate(insights, 1)) + """

## 3. Recommendations

""" + "\n".join(f"{i}. {t}" for i, t in enumerate(recs, 1)) + f"""

## 4. Spending by category

{md_table(cats, ['category', 'total_spent', 'avg_per_month', 'share_pct'], money=('total_spent', 'avg_per_month'), pct=('share_pct',))}

![Category spend](figures/04_category_spend.png)

## 5. Budget performance

{md_table(overview, ['category', 'total_budget', 'total_actual', 'utilisation_pct', 'months_over_budget', 'status'], money=('total_budget', 'total_actual'), pct=('utilisation_pct',))}

![Budget utilisation](figures/05_budget_utilisation.png)
![Budget heatmap](figures/06_budget_heatmap.png)

## 6. Cash flow

![Income vs expense](figures/01_income_vs_expense.png)
![Net savings](figures/02_net_savings.png)
![Cumulative savings](figures/03_cumulative_savings.png)

## 7. Behaviour

![Payment modes](figures/07_payment_modes.png)
![Weekday spend](figures/08_weekday_spend.png)
![50/30/20 rule](figures/09_50_30_20_rule.png)
![Needs vs wants](figures/10_needs_vs_wants_trend.png)

## 8. Data-quality work performed

""" + "\n".join(cleaning_log) + "\n"

    config.SUMMARY_REPORT_FILE.write_text(text, encoding="utf-8")
    print(f"Markdown report saved -> {config.SUMMARY_REPORT_FILE}")


def main():
    config.ensure_folders()
    df, budget = analysis.load_transactions(), analysis.load_budget()
    build_excel_report(df, budget)
    build_markdown_report(df, budget)


if __name__ == "__main__":
    main()
