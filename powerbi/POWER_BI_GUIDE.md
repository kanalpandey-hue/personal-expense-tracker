# Power BI Dashboard: Step-by-Step Guide

This guide shows how to build the **Personal Expense Tracker** dashboard in Power BI Desktop, using the ready-made CSV files in `powerbi/data/`. It takes about 45–60 minutes the first time.

---

## 0. Before you start

- **Power BI Desktop is free, but it runs only on Windows.** On a Mac, use a Windows PC (a college lab is fine) or a Windows virtual machine. Download it from the Microsoft Store or https://powerbi.microsoft.com/desktop.
- Copy the **whole `powerbi` folder** to the Windows computer.

### What is in this folder

| File | Rows | What it contains |
|---|---|---|
| `data/transactions.csv` | 1,275 | Every bank transaction (income and expenses) |
| `data/budget_vs_actual.csv` | 288 | Budget vs actual spending for 12 categories × 24 months |
| `data/categories.csv` | 16 | One row per category, with its type and group |
| `data/months.csv` | 24 | One row per month (Jan 2024 to Dec 2025) with labels |
| `prepare_powerbi_data.py` | – | The script that created the CSVs from the project's cleaned data |
| `POWER_BI_GUIDE.md` | – | This guide |

All the data comes from the project's existing cleaned dataset (`data/processed/transactions_clean.csv`) and budget file. The script checks that its totals match the Python analysis, the SQL results and the Streamlit dashboard.

### How the tables connect (star schema)

```
        months  (1 row per month)          categories  (1 row per category)
            │ year_month                        │ category
      ┌─────┴──────────────┐            ┌───────┴──────────────┐
      ▼                    ▼            ▼                      ▼
 transactions        budget_vs_actual  transactions      budget_vs_actual
```

- **months** and **categories** are small *lookup* tables.
- **transactions** and **budget_vs_actual** are *fact* tables that hold the numbers.
- Both fact tables connect to the same lookup tables, so **one Month slicer and one Category slicer filter every chart**.
- The two fact tables are **not** connected to each other directly.

---

## 1. Import the data

1. Open Power BI Desktop and select **Blank report**.
2. **Home → Get data → Text/CSV** → choose `data/transactions.csv` → click **Transform Data**, not Load. This opens the **Power Query Editor**, where you can check the column types.
3. In the Power Query Editor, choose **Home → New Source → Text/CSV** and add the other three files: `budget_vs_actual.csv`, `categories.csv`, `months.csv`.
4. Check the **data type** of each column. The icon left of each column name shows the type; click the icon to change it.

| Table | Column | Correct type |
|---|---|---|
| transactions | `date` | **Date** |
| transactions | `amount` | **Decimal Number** |
| transactions | all other columns | Text |
| budget_vs_actual | `budget_amount`, `actual_spent`, `variance`, `utilisation_pct` | **Decimal Number** |
| budget_vs_actual | `year_month`, `category`, `status` | Text |
| categories | all columns | Text |
| months | `year` | **Whole Number** |
| months | all other columns | Text |

> ⚠️ **Important:** Power BI often changes `year_month` (e.g. `2024-01`) into a **Date** automatically. Set `year_month` back to **Text** in **all three tables** (transactions, budget_vs_actual, months). If the types differ between tables, the relationships will not work.

5. Click **Home → Close & Apply**.

---

## 2. Create the relationships

1. Click the **Model view** icon on the left sidebar (it looks like three connected boxes).
2. Power BI may have created some relationships automatically. Open **Home → Manage relationships**, and make sure there are **exactly these 4**. Delete any others.

| From (one side) | To (many side) | Cardinality | Cross filter |
|---|---|---|---|
| `months[year_month]` | `transactions[year_month]` | One to many (1:*) | Single |
| `months[year_month]` | `budget_vs_actual[year_month]` | One to many (1:*) | Single |
| `categories[category]` | `transactions[category]` | One to many (1:*) | Single |
| `categories[category]` | `budget_vs_actual[category]` | One to many (1:*) | Single |

To add a missing relationship, **drag** the column from the lookup table (for example `months` → `year_month`) and drop it onto the same column in the fact table.

✅ When it is correct, each line has a **1** at the lookup-table end and a ***** at the fact-table end.

---

## 3. Create the measures

A **measure** is a small formula that Power BI recalculates every time you click a filter. We need measures because `transactions[amount]` contains both income and expenses, so a plain "Sum of amount" would add them together, which is wrong.

Go to **Report view**, select the `transactions` table in the **Data** pane, click **Home → New measure**, type the formula and press Enter. Repeat for each:

```DAX
Total Expense = CALCULATE ( SUM ( transactions[amount] ), transactions[txn_type] = "Debit" )
```
```DAX
Total Income = CALCULATE ( SUM ( transactions[amount] ), transactions[txn_type] = "Credit" )
```
```DAX
Net Savings = [Total Income] - [Total Expense]
```
```DAX
Savings Rate % = DIVIDE ( [Net Savings], [Total Income] )
```
```DAX
Budget Used % = DIVIDE ( SUM ( budget_vs_actual[actual_spent] ), SUM ( budget_vs_actual[budget_amount] ) )
```

**Formatting:** click each measure, then in **Measure tools**:
- `Total Expense`, `Total Income`, `Net Savings` → **Currency**, symbol **₹ English (India)**, 0 decimal places.
- `Savings Rate %`, `Budget Used %` → **Percentage**, 1 decimal place.

`DIVIDE()` is used instead of `/` because it safely returns blank instead of an error when a filter leaves no income.

---

## 4. Sort months correctly (one-time step)

Month names like "Apr 2024" would sort alphabetically, so April would come before January. To fix this:

1. Go to **Data view** (table icon on the left) and open the `months` table.
2. Click the `month_label` column → **Column tools → Sort by column → `year_month`**.

Now "Jan 2024, Feb 2024, …" appears in calendar order everywhere.

---

## 5. Page layout

Suggested layout for one page (16:9):

```
┌───────────────────────────────────────────────────────────────────────┐
│  Personal Expense Tracker & Budget Dashboard  (title text box)        │
│  [ Year ]   [ Month ▾ ]   [ Category ▾ ]   [ Payment Mode ▾ ]         │  ← slicers
├─────────────┬─────────────┬─────────────┬─────────────┬───────────────┤
│Total Income │Total Expense│ Net Savings │Savings Rate%│ Budget Used % │  ← cards
├─────────────┴─────────────┴──────┬──────┴─────────────┴───────────────┤
│ 1. Monthly Spending              │ 2. Spending by Category            │
│    (column chart)                │    (pie chart)                     │
├──────────────────────────────────┼────────────────────────────────────┤
│ 3. Budget vs Actual by Category  │ 4. Monthly Income vs Expense Trend │
│    (clustered bar chart)         │    (line chart)                    │
└──────────────────────────────────┴────────────────────────────────────┘
```

### KPI cards (top row)

Insert a **Card** visual for each of the 5 measures by dragging the measure into **Fields**. In **Format → Callout value**, set **Display units = None**, so you see the full amount instead of "1.88M". The comma grouping (₹18,83,674 or ₹1,883,674) depends on your Windows region settings. Both are the same number.

---

## 6. The four charts

Always use the **months** and **categories** columns for axes and legends (not the columns inside the fact tables). This is what makes the slicers filter every chart.

### Chart 1: Monthly spending (column chart)
1. Click an empty area → **Visualizations → Clustered column chart**.
2. **X-axis:** `months[month_label]`  **Y-axis:** `[Total Expense]`.
3. Click **… (More options) → Sort axis → month_label**, then **Sort ascending**.
4. Format → title: *Monthly Spending*. Set the column colour to orange `#EB6834`.

### Chart 2: Spending by category (pie chart)
1. **Visualizations → Pie chart**.
2. **Legend:** `categories[category]`  **Values:** `[Total Expense]`.
   Income categories such as Salary disappear automatically, because their Total Expense is blank.
3. Format → **Detail labels → Label contents: Category, percent of total**.
4. *Optional tidy-up:* 12 slices is a lot. In the **Filters** pane, set `category` to **Top N = 6** by `Total Expense`.

### Chart 3: Budget vs actual (clustered bar chart)
1. **Visualizations → Clustered bar chart**.
2. **Y-axis:** `categories[category]`
   **X-axis:** `budget_vs_actual[budget_amount]` **and** `budget_vs_actual[actual_spent]`. Both should show as *Sum*.
3. Rename the fields inside the visual (double-click them in the Fields well) to **Budget** and **Actual**.
4. Colours: Budget = light grey `#C3C2B7`, Actual = blue `#2A78D6`.
5. Sort by **Actual**, descending. A category whose Actual bar is longer than its Budget bar is **over budget**.
6. In the **Filters** pane for this visual, filter `categories[category_type]` = **Expense**, so income categories don't appear as empty rows.

### Chart 4: Monthly trend (line chart)
1. **Visualizations → Line chart**.
2. **X-axis:** `months[month_label]`  **Y-axis:** `[Total Income]` and `[Total Expense]`.
3. Sort the axis by `month_label` ascending, as in Chart 1.
4. Format → **Markers: On**. Colours: Income blue `#2A78D6`, Expense orange `#EB6834`.
5. *Optional:* in the **Analytics** pane (magnifying-glass icon), add an **Average line** for Total Expense.

---

## 7. Filters and slicers

A **slicer** is an on-page filter that the viewer can click. Add each one with **Visualizations → Slicer**, then drag a field into it:

| Slicer | Field | Suggested style (Format → Slicer settings) |
|---|---|---|
| Year | `months[year]` | **Tile** (buttons: 2024 / 2025) |
| Month | `months[month_label]` | **Dropdown**, multi-select allowed |
| Category | `categories[category]` | **Dropdown**, with "Select all" turned on |
| Payment Mode | `transactions[payment_mode]` | **Dropdown** |

**Using them:** click a value to filter, Ctrl + click to select several, and use the **eraser icon** on the slicer to clear it.

**Good to know (and a good viva answer):**
- The Year, Month and Category slicers filter **all** visuals, because they come from the shared lookup tables.
- The **Payment Mode** slicer filters only the transaction visuals (cards, Charts 1, 2 and 4). It does **not** change Chart 3, because the budget is planned per category, not per payment method.
- The **Filters pane** (right side) is for filters the viewer should *not* change, like the "Expense only" filter on Chart 3. Slicers are for filters the viewer *should* change.

---

## 8. Check your numbers ✅

Compare your dashboard with these values from the Python analysis.

**No slicers selected**

| Visual | Expected value |
|---|---|
| Total Income | ₹18,83,674 (1,883,674.03) |
| Total Expense | ₹14,60,802 (1,460,802.19) |
| Net Savings | ₹4,22,872 (422,871.84) |
| Savings Rate % | 22.4% |
| Budget Used % | 97.2% |
| Pie: largest slices | Rent 25.3%, Shopping 13.1%, Groceries 11.2%, Food & Dining 10.1% |
| Budget vs Actual: Shopping | Budget 1,56,000 · Actual 1,91,944.01 (over budget) |
| Budget vs Actual: Groceries | Budget 1,98,000 · Actual 1,62,982.70 (within budget) |

**With a slicer selected**

| Slicer | Check | Expected |
|---|---|---|
| Year = 2024 | Total Expense | ₹7,01,472.46 |
| Month = Jan 2024 | Total Expense / Total Income | ₹51,866.04 / ₹68,000.00 |
| Month = Mar 2025 | Net Savings | **−₹5,414.23** (a deficit month) |
| Month = Oct 2025 | Total Expense / Total Income | ₹71,274.71 / ₹86,060.00 |
| Category = Shopping | Total Expense | ₹1,91,944.01 |
| Payment Mode = UPI | Total Expense | ₹6,02,763.80 |

If your numbers differ, see **Troubleshooting** below.

---

## 9. Save and export

- **File → Save as** → `powerbi/Expense_Dashboard.pbix`.
- **File → Export → Export to PDF** gives you a PDF for the report.
- Take screenshots (Windows: **Win + Shift + S**) for the README and the PowerPoint.

If the project data ever changes: run `python powerbi/prepare_powerbi_data.py` on your Mac, copy the new CSVs to the same folder, and click **Home → Refresh** in Power BI.

---

## 10. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Totals are far too large | Used `amount` directly, which adds income and expenses | Use the `[Total Expense]` / `[Total Income]` measures |
| A slicer doesn't change a chart | That chart uses a fact-table column on its axis, or a relationship is missing | Use `months[...]` / `categories[...]` on axes; recheck **Manage relationships** |
| Can't create a relationship / "many-to-many" warning | `year_month` is Date in one table and Text in another | Set `year_month` to **Text** in all three tables (Transform data) |
| Months in A-Z order (Apr, Aug, Dec…) | Sort-by-column not set | Repeat **Section 4** and **Sort axis** on the chart |
| A "(Blank)" category or month appears | A relationship is missing or wrong | Recheck the 4 relationships in **Section 2** |
| Amounts 100× too big, or dates missing | Computer's regional format uses `,` for decimals or day-first dates | Transform data → right-click column → **Change Type → Using Locale… → English (United States)** |
| "File not found" after moving the folder | Power BI remembers the old file path | **Transform data → Data source settings → Change Source** |

---

## 11. How to explain it in your viva

- **Why a star schema?** Lookup tables (months, categories) hold each value once. Fact tables hold the numbers. One slicer can then filter several fact tables, which is the standard Power BI design.
- **Why measures instead of plain columns?** The `amount` column mixes income and expenses. Measures such as `Total Expense` apply the right filter and recalculate correctly for every slicer selection.
- **Why `DIVIDE()`?** It avoids divide-by-zero errors when a filter leaves no data.
- **Where do the numbers come from?** From the project's cleaned dataset, prepared by `prepare_powerbi_data.py`. That script reuses the same Python analysis functions as the Streamlit dashboard, so both dashboards show identical totals.
