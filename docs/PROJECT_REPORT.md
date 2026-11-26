# Project Report
## Personal Expense Tracker and Budget Dashboard

| | |
|---|---|
| **Programme** | HCL Tech Data Analytics Project |
| **Domain** | Banking and Finance |
| **Student** | *[Your Name]*, B.Tech CSE (2nd Year), ABES Engineering College |
| **Roll No.** | *[Your Roll Number]* |
| **Guide / Mentor** | *[Mentor Name]* |

---

## Abstract

This project builds an end-to-end data analytics solution for personal finance. Twenty-four months of bank transactions for a salaried professional are generated with realistic spending behaviour and deliberate data-quality defects. The data is cleaned using a logged nine-step pipeline, enriched with engineered features, stored in a relational SQLite database, and analysed with Python (pandas) and SQL. Results are delivered through 10 static charts, a formatted 11-sheet Excel workbook and an interactive Streamlit dashboard. The dashboard offers budget alerts, a what-if savings simulator and live expense entry. For the simulated user, the analysis finds a 22.4% savings rate, persistent overspending on Shopping (16 of 24 months over budget) and a 1.6× festive-season spending spike, and it produces specific recommendations.

## 1. Introduction

Digital payments (especially UPI) have made spending effortless but hard to track. A typical bank statement lists hundreds of small transactions and gives no view by category, no comparison with a budget, and no warning before overspending. This project applies the data-analytics lifecycle (**collect → clean → store → analyse → visualise → recommend**) to solve that problem.

### 1.1 Objectives
1. Model realistic personal banking transactions.
2. Detect and fix common data-quality issues, and document each fix.
3. Compute financial KPIs: income, expense, savings and savings rate.
4. Compare actual spending with a monthly budget and raise alerts.
5. Answer business questions in SQL.
6. Present results in Excel, static charts and an interactive dashboard.

### 1.2 Scope
A single user with 12 expense categories, 4 income categories and 5 payment modes, over 24 months (Jan 2024 to Dec 2025), in Indian Rupees.

## 2. Background concepts

- **Budget utilisation** = actual spend ÷ budget × 100. In this project: < 80% = *Within Budget*, 80–100% = *Near Limit*, > 100% = *Over Budget*.
- **Variance** = budget − actual. A positive value means money saved; a negative value means overspent.
- **50/30/20 rule**: a widely used guideline that allocates 50% of income to needs, 30% to wants and 20% to savings.
- **IQR outlier rule**: a value above Q3 + 1.5 × IQR is unusually large for its group.
- **Fixed vs variable costs**: fixed costs (rent, insurance, subscriptions, utilities) recur every month; variable costs depend on behaviour.

## 3. System architecture

```
 generate_dataset.py          data_cleaning.py            sql_analysis.py
 ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
 │ transactions_raw │──────▶│ 9 cleaning steps │──────▶│ SQLite database  │
 │ monthly_budget   │        │ + feature eng.   │        │ 10 SQL queries   │
 └──────────────────┘        └────────┬─────────┘        └──────────────────┘
                                      │ transactions_clean.csv
                                      ▼
                             ┌──────────────────┐
                             │   analysis.py    │  (single source of truth
                             │ KPIs · budget ·  │   for every number)
                             │ insights         │
                             └──┬──────┬─────┬──┘
                ┌───────────────┘      │     └────────────────┐
                ▼                      ▼                      ▼
      visualizations.py      report_generator.py       dashboard/app.py
      10 PNG charts          Excel (11 sheets) + MD     Streamlit + Plotly
```

`main.py` runs every stage in order. `config.py` holds all paths and thresholds.

## 4. Dataset

### 4.1 Generation logic
- **Income:** salary ₹68,000/month, rising to ₹76,160 after a 12% hike in April 2025; freelance payments in about 40% of months; quarterly bank interest; occasional refunds.
- **Fixed bills:** rent (₹15,000, revised to ₹15,750 in 2025), Netflix, Spotify, Jio, Amazon Prime, LIC premium; annual Star Health premium (₹18,500) every March.
- **Utilities:** electricity 2–2.8× higher in Apr–Sep (air-conditioning); cooking gas higher in winter.
- **Variable spending:** Poisson-distributed counts per category, with merchant-specific price ranges.
- **Seasonality:** Diwali shopping (Oct–Nov), Republic Day sales (Jan), holiday travel (May, Jun, Dec), monsoon healthcare (Jul–Aug), course fees (Jan, Jul).
- **Payment modes:** chosen by category-specific probabilities (e.g. rent → Net Banking, food → UPI).

### 4.2 Budget
A per-category monthly plan, revised for 2025 after the salary hike. The March insurance budget includes the annual premium (sinking-fund approach).

## 5. Data cleaning

| # | Problem found | Rows affected | Fix |
|---|---|---|---|
| 1 | Duplicate transactions | 25 | `drop_duplicates()` on full row and on `transaction_id` |
| 2 | Dates in `DD/MM/YYYY` and `DD-Mon-YYYY` | 191 | Explicit format list, day-first |
| 3 | Amounts as text (`₹1,250.00`) | 102 | Strip ₹ and commas, convert to float |
| 4 | Negative debit amounts | 11 | Absolute value (direction is stored in `txn_type`) |
| 5 | `DR` / `CR` labels | 51 | Mapped to Debit / Credit |
| 6 | Misspelt categories (`GROCERIES`, `food and dining`) | 102 | Lookup table of official names |
| 7 | Missing categories | 25 | Filled with merchant's most frequent category (25/25 recovered) |
| 8 | Missing payment modes | 38 | Set to `Unknown` (not guessed) |
| 9 | Typing-error outliers (₹31,950 at Swiggy, ₹60,631 at Starbucks, ₹70,597 at Domino's) | 3 | Removed: amount > 20× merchant median |
| – | Genuinely large purchases | 69 | Flagged with IQR rule, **kept** |

Result: **1,303 raw rows → 1,275 clean rows, 19 columns, 0 missing values.** The full log is in `data/processed/cleaning_log.txt`.

**Engineered features:** `year`, `month`, `month_name`, `year_month`, `quarter`, `day_of_week`, `is_weekend`, `signed_amount`, `expense_type` (Income/Essential/Discretionary), `cost_nature` (Income/Fixed/Variable), `is_large_spend`.

## 6. Database design (SQLite)

| Table | Key | Purpose |
|---|---|---|
| `categories` | `category_name` (PK) | Category group & nature |
| `transactions` | `transaction_id` (PK), FK → categories | All clean transactions |
| `budgets` | (`month`, `category`) composite PK | Planned monthly budget |

CHECK constraints enforce positive amounts and valid types. Indexes on `year_month` and `category` speed up grouping.

### 6.1 SQL business questions (`sql/analysis_queries.sql`)

| Query | Question | SQL concepts |
|---|---|---|
| Q1 | Monthly income, expense, savings | `CASE` inside `SUM`, `GROUP BY` |
| Q2 | Spend and share per category | Sub-query for total |
| Q3 | Budget vs actual per month/category | `LEFT JOIN`, `COALESCE`, `CASE` status |
| Q4 | How often each category overspends | CTE (`WITH`) |
| Q5 | Payment-mode usage | Aggregation, share % |
| Q6 | Top 10 merchants | `ORDER BY … LIMIT` |
| Q7 | Weekend vs weekday spending | `JOIN` with categories |
| Q8 | Month-over-month change | Window function `LAG()` |
| Q9 | Top 5 categories per year | Window function `RANK() OVER (PARTITION BY)` |
| Q10 | Needs vs wants per year | `JOIN` + grouping |

Results are saved to `reports/sql_outputs/`. An automated test confirms the SQL totals equal the pandas totals.

## 7. Analysis & results

### 7.1 KPIs (Jan 2024 to Dec 2025)

| Metric | Value |
|---|---|
| Total income | ₹18,83,674 |
| Total expense | ₹14,60,802 |
| Net savings | ₹4,22,872 |
| Savings rate | 22.4% |
| Avg monthly income / expense | ₹78,486 / ₹60,867 |
| Expense transactions | 1,221 (avg ₹1,196) |

### 7.2 Findings
1. **Concentration:** Rent (25.3%), Shopping (13.1%) and Groceries (11.2%) account for about half of all spending.
2. **Budget discipline:** Shopping exceeded its budget in 16 of 24 months (123% utilisation). Education (120%), Entertainment (107%), Food & Dining (107%) and Healthcare (102%) are also over budget overall. Utilities (80%) and Travel (70%) stay within budget.
3. **Deficit months:** Jul 2024 and Mar 2025, where spending exceeded income. Best month: Feb 2024 (₹45,769 saved).
4. **Seasonality:** Shopping in Oct–Nov runs at 1.6× a normal month; wants spike in festive and holiday months.
5. **Payments:** 94.6% of spending is digital; UPI handles 41% of value and about 55% of transactions.
6. **50/30/20:** Needs 50.3%, Wants 27.3%, Savings 22.4%. This is a healthy profile overall.

### 7.3 Recommendations
1. Re-base the Shopping budget or create a separate festive fund for Oct–Nov.
2. Cap Education spending per course season, or budget it as an annual amount.
3. Reducing food-delivery spending by 20% would save about ₹14,800 a year.
4. Automate a SIP/RD on salary day so savings happen first ("pay yourself first").

## 8. Visualisation & dashboard

**Static charts (`reports/figures/`):** income vs expense, net savings, cumulative savings, category spend, budget utilisation, budget heatmap, payment modes, weekday spend, 50/30/20, needs vs wants trend. The charts use a colour-blind-safe palette with consistent meaning: blue = income/savings, orange = expense, red = over budget.

**Excel workbook:** KPI summary with native Excel charts; monthly, category, budget, payment, merchant and year-over-year sheets; green/amber/red conditional formatting on budget status; clean data and a data dictionary.

**Streamlit dashboard:** 6 tabs (Overview, Categories, Budget Tracker, Insights, Transactions, Add Expense), sidebar filters, budget alerts, a what-if simulator, search, CSV export and live data entry with validation.

## 9. Testing

`tests/test_project.py` contains **23 pytest tests**. They cover date, amount and category parsing; budget-status thresholds; data-quality checks (no missing values, unique IDs, positive amounts, valid categories); KPI consistency; category shares summing to 100%; budget table coverage; SQL-vs-pandas agreement; and insight generation. **All 23 pass.**

## 10. Challenges faced

See README §10. The main ones were: ambiguous date formats; separating typing errors from real large purchases; annual bills distorting monthly budgets; and keeping numbers consistent across three outputs (solved with a single analysis module and cross-check tests).

## 11. Conclusion

The project shows the complete analytics workflow on a banking-domain problem. Raw, inconsistent transaction data was turned into a trustworthy dataset. The analysis answers concrete questions in both Python and SQL, and the results are delivered in the formats stakeholders use (Excel, reports and an interactive dashboard). The budget tracker and simulator turn the analysis into decisions a user can act on.

## 12. Future enhancements

Real bank-statement import, ML-based auto-categorisation of narrations, spending forecasts, multi-user accounts with a cloud database, and push alerts when a budget crosses 80%.

## 13. References

1. pandas documentation: https://pandas.pydata.org/docs/
2. Streamlit documentation: https://docs.streamlit.io/
3. Plotly Python documentation: https://plotly.com/python/
4. SQLite documentation: https://www.sqlite.org/docs.html
5. NPCI UPI product statistics: https://www.npci.org.in/what-we-do/upi/product-statistics
6. Warren, E. & Tyagi, A. W. (2005). *All Your Worth* (origin of the 50/30/20 rule).
