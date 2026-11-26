# 💰 Personal Expense Tracker & Budget Dashboard

**HCL Tech Data Analytics Project** · Domain: **Banking & Finance**
B.Tech CSE (2nd Year) · ABES Engineering College

A complete data-analytics pipeline that turns 24 months of raw, messy bank transactions into clean data, SQL insights, an Excel report, publication-quality charts and an **interactive budget dashboard**.

**Key features**

- Realistic synthetic bank dataset (1,303 raw transactions, Jan 2024 – Dec 2025)
- 9-step data-cleaning pipeline with a cleaning log
- Budget vs actual tracking with over-budget alerts
- 10 business questions answered in SQL (SQLite) and Oracle SQL, plus a PL/SQL budget package
- Jupyter Notebook walk-through of the analysis
- Interactive Streamlit dashboard and a Power BI dashboard guide
- Excel report, 10 charts and 23 automated tests

---

## 1. Problem statement

Most young salaried people in India pay through UPI, cards and net banking, so their spending is scattered across many small transactions. They don't know **where their money goes**, **which budgets they break**, or **whether they save enough**. Bank statements are raw lists and hard to analyse.

**Goal:** build a tool that cleans transaction data, tracks spending against a monthly budget, and presents clear, actionable insights on a dashboard.

## 2. Objectives

1. Create a realistic transaction dataset (income, fixed bills, variable spending, seasonality).
2. Clean real-world data problems: duplicates, mixed date formats, text amounts, inconsistent categories, missing values and outliers.
3. Analyse spending by month, category, payment mode and weekday.
4. Track **budget vs actual** for every category and month, with alerts.
5. Answer business questions using **SQL** (joins, CTEs, window functions).
6. Deliver an **Excel report**, **static charts** and an **interactive Streamlit dashboard**.
7. Generate plain-English **insights and recommendations**.

## 3. Tools & technologies

| Purpose | Tool |
|---|---|
| Language | Python 3 |
| Data processing | pandas, NumPy |
| Database & queries | SQLite (`sqlite3`), SQL |
| Static charts | Matplotlib |
| Interactive dashboard | Streamlit + Plotly |
| Excel reporting | openpyxl (formatted sheets, native Excel charts, conditional formatting) |
| Notebook analysis | Jupyter Notebook |
| Oracle database | Oracle SQL & PL/SQL (Oracle 19c or later, Oracle Live SQL) |
| BI dashboard | Microsoft Power BI Desktop |
| Testing | pytest |

## 4. Project structure

```
personal expense tracker/
├── main.py                        ← runs the whole pipeline (one command)
├── requirements.txt
├── data/
│   ├── raw/
│   │   ├── transactions_raw.csv   ← messy bank export (1,303 rows)
│   │   └── monthly_budget.csv     ← planned budget, 12 categories × 24 months
│   └── processed/
│       ├── transactions_clean.csv ← cleaned + 11 engineered features
│       ├── cleaning_log.txt       ← what every cleaning step fixed
│       └── expense_tracker.db     ← SQLite database
├── src/
│   ├── config.py                  ← paths & settings in one place
│   ├── generate_dataset.py        ← creates the realistic dataset
│   ├── data_cleaning.py           ← 9-step cleaning pipeline
│   ├── analysis.py                ← all KPIs, budget logic & insights
│   ├── sql_analysis.py            ← loads SQLite + runs SQL queries
│   ├── visualizations.py          ← 10 report charts (PNG)
│   └── report_generator.py        ← Excel workbook + Markdown report
├── sql/
│   ├── schema.sql                 ← table design (3 tables, keys, checks)
│   ├── analysis_queries.sql       ← 10 business questions in SQL
│   └── oracle/                    ← Oracle SQL + PL/SQL scripts 01–06 (see its README)
├── notebooks/
│   └── expense_tracker_analysis.ipynb ← step-by-step analysis notebook
├── dashboard/
│   └── app.py                     ← interactive Streamlit dashboard
├── powerbi/
│   ├── POWER_BI_GUIDE.md          ← step-by-step Power BI guide
│   ├── prepare_powerbi_data.py    ← creates the Power BI CSVs
│   └── data/                      ← 4 ready-to-import CSV files
├── reports/
│   ├── Expense_Analysis_Report.xlsx
│   ├── insights_summary.md
│   ├── figures/                   ← 10 charts
│   └── sql_outputs/               ← CSV result of every SQL query
├── docs/
│   └── PROJECT_REPORT.md          ← full write-up for submission
└── tests/
    └── test_project.py            ← 23 automated tests
```

## 5. How to run

```bash
# 1. (one time) create a virtual environment and install libraries
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. run the full pipeline (dataset → cleaning → analysis → SQL → charts → reports)
python main.py

# 3. open the interactive dashboard in your browser
streamlit run dashboard/app.py

# 4. (optional) run the automated tests
python -m pytest tests -v
```

Each script in `src/` can also be run on its own, e.g. `python src/analysis.py`.

### Jupyter Notebook

```bash
jupyter notebook notebooks/expense_tracker_analysis.ipynb
```

Then choose **Kernel → Restart Kernel and Run All Cells**. The notebook only reads the project data; run `python main.py` first if the `data/processed/` files are missing.

### Oracle SQL & PL/SQL

The scripts are in `sql/oracle/`. Run them in this order in **Oracle Live SQL** (free, in the browser) or SQL Developer:

1. `01_create_schema.sql` – tables, sequences, trigger, indexes
2. `02_insert_reference_data.sql` – categories and budgets
3. `03_insert_transactions.sql` – all cleaned transactions
4. `04_budget_plsql.sql` – PL/SQL package `PKG_BUDGET`
5. `05_analysis_queries.sql` – 10 business questions
6. `06_create_views.sql` – 2 reporting views

**Status:** all six scripts have been executed successfully in Oracle Live SQL. The PL/SQL package `PKG_BUDGET` and both reporting views (`v_monthly_summary`, `v_budget_status`) were verified as **VALID**.

Each script lists its expected results in comments. Full details are in [`sql/oracle/README.md`](sql/oracle/README.md).

### Power BI dashboard

**Implementation status**

- **Data prepared and validated:** the Power BI datasets (`transactions`, `categories`, `months`, `budget_vs_actual`) and supporting CSV files are generated in `powerbi/data/` and checked against the cleaned project data.
- **Guide included:** [`powerbi/POWER_BI_GUIDE.md`](powerbi/POWER_BI_GUIDE.md) contains the DAX measures and step-by-step instructions to build the dashboard.
- **No `.pbix` file:** the report file was not generated because Power BI Desktop is not natively supported on macOS, where this project was developed.
- **Interactive alternative:** the project includes a working Streamlit dashboard (`streamlit run dashboard/app.py`) with the same core analysis: KPIs, filters, category spending and budget vs actual.

To build the Power BI report on Windows:

1. Copy the `powerbi/` folder to a Windows PC (Power BI Desktop runs only on Windows).
2. In Power BI Desktop, import the 4 CSV files from `powerbi/data/`.
3. Follow [`powerbi/POWER_BI_GUIDE.md`](powerbi/POWER_BI_GUIDE.md) for relationships, measures, charts and slicers.

To rebuild the CSV files after changing the data: `python powerbi/prepare_powerbi_data.py`.

## 6. Dataset

A simulated salaried professional in Delhi, **Jan 2024 to Dec 2025**. The data is synthetic because real bank statements are private. The generator is seeded, so it reproduces the same data on every run.

| Column | Meaning |
|---|---|
| `transaction_id` | Unique ID |
| `date` | Transaction date |
| `description` | Bank narration |
| `category` | 12 expense + 4 income categories |
| `amount` | Amount in ₹ |
| `txn_type` | Debit (out) / Credit (in) |
| `payment_mode` | UPI, Debit Card, Credit Card, Net Banking, Cash |
| `merchant` | Swiggy, DMart, IRCTC, BSES, … |

**Realistic behaviour built in:** salary hike in April 2025 · rent revision in Jan 2025 · summer electricity bills (AC) · Diwali shopping spike (Oct–Nov) · holiday travel (May/Jun/Dec) · annual health-insurance premium in March · course fees in Jan/Jul.

**Deliberate data-quality problems** (to demonstrate cleaning): 25 duplicate rows, 191 non-standard dates, 102 amounts stored as text (`"₹1,250.00"`), 11 negative amounts, 51 `DR`/`CR` labels, 102 misspelt categories, 25 missing categories, 38 missing payment modes, 3 typing-error outliers.

## 7. Methodology

1. **Data generation**: `generate_dataset.py`
2. **Data cleaning**: `data_cleaning.py`. Explicit date-format parsing (avoids the 05/01 vs 01/05 confusion) · currency-text parsing · category mapping table · missing categories recovered from the merchant's usual category · outliers > 20× merchant median removed as typing errors · genuine large spends flagged with the IQR rule but kept.
3. **Feature engineering**: year, month, quarter, weekday, weekend flag, signed amount, Essential/Discretionary, Fixed/Variable.
4. **Analysis**: `analysis.py`. KPIs, monthly cash flow, category share, budget vs actual, 50/30/20 rule, payment behaviour, year-over-year, automatic insights.
5. **SQL**: `sql_analysis.py`. The same questions answered with SQL (JOIN, CASE, CTE, `LAG`, `RANK`). A test checks that SQL and pandas agree.
6. **Visualisation & reporting**: Matplotlib charts, formatted Excel workbook, Streamlit dashboard.

## 8. Key results (from the generated data)

| Metric | Value |
|---|---|
| Total income (24 months) | ₹18,83,674 |
| Total expense | ₹14,60,802 |
| Net savings | ₹4,22,872 |
| **Savings rate** | **22.4%** (meets the 20% goal) |
| Avg monthly spend | ₹60,867 |
| Top category | Rent (25.3% of spending) |

**Top insights**
- Rent, Shopping and Groceries make up **~50%** of all spending.
- **Shopping went over budget in 16 of 24 months** (123% of budget used overall). This is the biggest leak.
- Education (120%), Entertainment (107%) and Food & Dining (107%) are also over budget.
- Spending exceeded income in **2 months** (Jul 2024, Mar 2025). March is driven by the annual insurance premium.
- Festive effect: Shopping in Oct–Nov is **1.6×** a normal month.
- **94.6% of spending is digital**; UPI alone is 41%.
- 50/30/20 check: Needs 50.3% · Wants 27.3% · Savings 22.4%.

**Recommendations:** tighten the Shopping budget or keep a dedicated festive fund; cut food delivery 20% to save about ₹14.8k/year; automate a SIP/RD on salary day.

## 9. Dashboard features (`streamlit run dashboard/app.py`)

| Tab | What it shows |
|---|---|
| 📊 Overview | KPI cards, income vs expense, monthly savings (deficits in red), cumulative savings, 50/30/20 |
| 🗂️ Categories | Spend by category, needs vs wants trend, category × month heatmap, top merchants, payment modes |
| 🎯 Budget Tracker | Pick any month → budget vs actual, **over-budget / near-limit alerts**, scorecard with progress bars, utilisation heatmap |
| 💡 Insights | Auto-generated insights + **what-if savings simulator** (sliders) |
| 📄 Transactions | Search, large-spend filter, CSV download |
| ➕ Add Expense | Log new income/expenses (validated); charts update instantly |

Sidebar filters: period, categories and payment modes. All charts are interactive, with hover, zoom and download.

## 10. Challenges & solutions

| Challenge | Solution |
|---|---|
| No access to real bank data (privacy) | Seeded, behaviour-driven synthetic data generator |
| Mixed date formats (`05/01/2024` ambiguity) | Explicit list of formats tried in order (day-first) |
| Amounts stored as text with ₹ and commas | Custom `parse_amount()` |
| Same category spelt many ways | Lookup table built from official names |
| Missing categories | Filled from the merchant's most frequent category |
| Telling typing errors apart from real big purchases | Two rules: > 20× merchant median = error (removed); IQR = genuine large spend (flagged, kept) |
| Annual bills distorting monthly budgets | Annual premium budgeted in its month (sinking-fund approach) |
| Keeping dashboard, SQL and Excel numbers consistent | One `analysis.py` used everywhere + automated tests (SQL = pandas) |

## 11. Success criteria: status

- [x] Raw data cleaned with **0 missing values** and **0 duplicate IDs** (tested)
- [x] Every cleaning action logged and quantified (`cleaning_log.txt`)
- [x] Budget vs actual for 12 categories × 24 months, with alerts
- [x] 10 SQL business queries, results match pandas (tested)
- [x] 10 report charts + 11-sheet Excel workbook with native charts
- [x] Interactive dashboard with filters, alerts, simulator and data entry
- [x] Whole pipeline reproducible with one command (`python main.py`, ~3 s)
- [x] 23 automated tests passing

## 12. Future scope

- Import real bank statements (CSV/PDF parsers for SBI, HDFC, ICICI formats)
- Auto-categorise new transactions with an ML text classifier on the narration
- Forecast next month's spending (moving average / ARIMA)
- Multi-user login and cloud database
- Email/WhatsApp alerts when a budget crosses 80%
