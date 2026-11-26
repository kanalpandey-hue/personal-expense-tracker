"""
generate_dataset.py
-------------------
Creates a REALISTIC synthetic dataset of personal bank transactions.

Why synthetic?
    Real bank statements contain private data, so we simulate a salaried
    young professional in India over 24 months (Jan 2024 - Dec 2025).

What makes it realistic?
    * Fixed monthly bills (rent, subscriptions, insurance EMI) on fixed dates
    * Variable spending (groceries, food delivery, fuel) at random times
    * Seasonal behaviour: Diwali shopping (Oct/Nov), summer electricity bills,
      holiday travel (May/Dec), college/course fees (Jan/Jul)
    * A salary hike in April 2025 (Indian appraisal cycle)

Why add "dirty" data on purpose?
    Real-world data is never clean. A data analytics project must show
    data cleaning skills, so we inject typical problems:
        - duplicate rows (same transaction exported twice)
        - mixed date formats  (2024-01-05, 05/01/2024, 05-Jan-2024)
        - amounts stored as text ("₹1,250.00")
        - inconsistent category spelling ("groceries ", "FOOD & DINING")
        - missing categories / payment modes
        - a few negative amounts (sign error) and extreme outliers

Run:  python src/generate_dataset.py
"""

import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

import config

# A fixed seed means we get the SAME dataset every time we run the script.
# This makes the project reproducible (important for evaluation).
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)

# ---------------------------------------------------------------------------
# Merchants for each category: (merchant name, min amount, max amount)
# ---------------------------------------------------------------------------
MERCHANTS = {
    "Groceries": [("BigBasket", 400, 2500), ("DMart", 600, 3000),
                  ("Blinkit", 150, 900), ("Local Kirana Store", 100, 700),
                  ("Zepto", 150, 800)],
    "Food & Dining": [("Swiggy", 180, 750), ("Zomato", 180, 800),
                      ("Haldiram's", 250, 1200), ("Starbucks", 300, 700),
                      ("Domino's", 300, 900), ("Office Canteen", 60, 200)],
    "Transportation": [("Uber", 120, 650), ("Ola", 100, 550),
                       ("Delhi Metro Recharge", 200, 500),
                       ("Indian Oil Petrol Pump", 500, 2000),
                       ("Rapido", 40, 180)],
    "Shopping": [("Amazon", 300, 3000), ("Flipkart", 300, 2800),
                 ("Myntra", 500, 2500), ("Decathlon", 700, 3000),
                 ("Croma", 1500, 9000)],
    "Entertainment": [("PVR Cinemas", 350, 1200), ("BookMyShow", 300, 2500),
                      ("Steam Games", 300, 1800), ("Bowling Alley", 500, 1500)],
    "Healthcare": [("Apollo Pharmacy", 150, 1500), ("1mg", 200, 1200),
                   ("Max Hospital", 800, 5000), ("Dental Clinic", 500, 3000)],
    "Travel": [("IRCTC", 600, 3500), ("MakeMyTrip", 3000, 12000),
               ("IndiGo Airlines", 3500, 9000), ("OYO Rooms", 1200, 5000)],
    "Education": [("Udemy", 449, 3500), ("Coursera", 2500, 4000),
                  ("Amazon Books", 300, 1500)],
}

# Fixed bills: (category, merchant, amount, day of month)
FIXED_MONTHLY_BILLS = [
    ("Rent", "House Rent - Landlord", 15000, 3),
    ("Subscriptions", "Netflix", 649, 7),
    ("Subscriptions", "Spotify", 119, 12),
    ("Subscriptions", "Jio Mobile Recharge", 349, 15),
    ("Subscriptions", "Amazon Prime", 299, 20),
    ("Insurance", "LIC Policy Premium", 2200, 10),
]

# Utilities change with season: base amount per merchant
UTILITIES = [
    ("BSES Electricity", 1200),   # rises in summer due to AC
    ("Airtel Broadband", 799),
    ("Indraprastha Gas (PNG)", 450),
    ("Delhi Jal Board", 250),
]

# How many times per month (average) each variable category occurs
MONTHLY_FREQUENCY = {
    "Groceries": 8,
    "Food & Dining": 12,
    "Transportation": 13,
    "Shopping": 2.5,
    "Entertainment": 2.5,
    "Healthcare": 1.2,
    "Education": 0.6,
    "Travel": 0.4,
}

# Which payment modes are common for which category (probabilities)
PAYMENT_PREFERENCE = {
    "Rent": {"Net Banking": 0.9, "UPI": 0.1},
    "Insurance": {"Net Banking": 0.7, "Debit Card": 0.3},
    "Subscriptions": {"Credit Card": 0.6, "UPI": 0.3, "Debit Card": 0.1},
    "Utilities": {"UPI": 0.6, "Net Banking": 0.3, "Credit Card": 0.1},
    "Travel": {"Credit Card": 0.6, "UPI": 0.2, "Net Banking": 0.2},
    "Shopping": {"Credit Card": 0.5, "UPI": 0.35, "Debit Card": 0.15},
    "default": {"UPI": 0.65, "Debit Card": 0.12, "Credit Card": 0.13, "Cash": 0.10},
}


def pick_payment_mode(category):
    """Choose a payment mode using the category's probability table."""
    table = PAYMENT_PREFERENCE.get(category, PAYMENT_PREFERENCE["default"])
    modes = list(table.keys())
    probs = list(table.values())
    return np.random.choice(modes, p=probs)


def seasonal_multiplier(category, month):
    """
    Return a number that scales spending up/down depending on the month.
    1.0 = normal month, 2.0 = double the usual spend.
    """
    if category == "Shopping" and month in (10, 11):       # Diwali / festive sales
        return 2.6
    if category == "Shopping" and month == 1:              # Republic Day sales
        return 1.3
    if category == "Travel" and month in (5, 6, 12):       # summer + year-end holidays
        return 4.0
    if category == "Food & Dining" and month in (10, 11, 12):  # festivals & parties
        return 1.3
    if category == "Healthcare" and month in (7, 8):       # monsoon illnesses
        return 1.8
    if category == "Education" and month in (1, 7):        # new course season
        return 3.0
    return 1.0


def random_day_in_month(year, month):
    """Pick a random calendar date inside a given month."""
    first = date(year, month, 1)
    # first day of next month minus one day = last day of this month
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    days_in_month = (next_month - first).days
    return first + timedelta(days=random.randint(0, days_in_month - 1))


def month_iter(start, end):
    """Yield (year, month) tuples from start to end (inclusive)."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def build_clean_transactions():
    """Create a list of clean transaction dictionaries."""
    rows = []

    for year, month in month_iter(START_DATE, END_DATE):
        # ---------------- INCOME ----------------
        # Salary hike of 12% from April 2025 (appraisal)
        salary = 68000 if (year, month) < (2025, 4) else 76160
        rows.append(dict(date=date(year, month, 1), description="Salary Credit - TechNova Pvt Ltd",
                         category="Salary", amount=salary, txn_type="Credit",
                         payment_mode="Net Banking", merchant="TechNova Pvt Ltd"))

        # Occasional freelance income (about 1 in 3 months)
        if random.random() < 0.40:
            rows.append(dict(date=random_day_in_month(year, month),
                             description="Freelance Project Payment",
                             category="Freelance",
                             amount=round(random.uniform(5000, 18000), -2),
                             txn_type="Credit", payment_mode="UPI",
                             merchant="Upwork Client"))

        # Quarterly savings-account interest
        if month in (3, 6, 9, 12):
            rows.append(dict(date=date(year, month, 28), description="Savings Interest Credit",
                             category="Interest", amount=round(random.uniform(600, 1400), 2),
                             txn_type="Credit", payment_mode="Net Banking",
                             merchant="Bank Interest"))

        # ---------------- FIXED BILLS ----------------
        for category, merchant, amount, day in FIXED_MONTHLY_BILLS:
            # Rent increases by 5% on renewal in Jan 2025
            if category == "Rent" and year == 2025:
                amount = 15750
            rows.append(dict(date=date(year, month, day), description=f"{merchant} Payment",
                             category=category, amount=amount, txn_type="Debit",
                             payment_mode=pick_payment_mode(category), merchant=merchant))

        # Annual health-insurance premium every March (tax-saving season)
        if month == 3:
            rows.append(dict(date=date(year, 3, 25), description="Star Health Annual Premium",
                             category="Insurance", amount=18500, txn_type="Debit",
                             payment_mode="Net Banking", merchant="Star Health Insurance"))

        # ---------------- UTILITIES ----------------
        for merchant, base in UTILITIES:
            amount = base
            if merchant == "BSES Electricity":
                # Summer (Apr-Sep) AC usage doubles the electricity bill
                if month in (4, 5, 6, 7, 8, 9):
                    amount = base * random.uniform(2.0, 2.8)
                else:
                    amount = base * random.uniform(0.8, 1.1)
            elif merchant == "Indraprastha Gas (PNG)" and month in (12, 1, 2):
                amount = base * 1.6  # more hot water / cooking gas in winter
            rows.append(dict(date=date(year, month, random.randint(5, 18)),
                             description=f"{merchant} Bill",
                             category="Utilities", amount=round(amount, 2), txn_type="Debit",
                             payment_mode=pick_payment_mode("Utilities"), merchant=merchant))

        # ---------------- VARIABLE SPENDING ----------------
        for category, avg_count in MONTHLY_FREQUENCY.items():
            multiplier = seasonal_multiplier(category, month)
            # Poisson distribution gives a realistic random count around the average
            # Seasonal effect works in two ways:
            #   - Shopping/Travel/Education/Healthcare: MORE transactions happen
            #   - Food & Dining: the SAME number of orders, but each is bigger
            if category == "Food & Dining":
                count = np.random.poisson(avg_count)
            else:
                # normal random purchases + a fixed number of extra
                # "planned" seasonal purchases (e.g. Diwali gifts, holiday trip)
                extra = round(avg_count * (multiplier - 1))
                count = np.random.poisson(avg_count) + extra
            for _ in range(count):
                merchant, low, high = random.choice(MERCHANTS[category])
                amount = random.uniform(low, high)
                if category == "Food & Dining":
                    amount *= multiplier
                rows.append(dict(date=random_day_in_month(year, month),
                                 description=f"Purchase at {merchant}",
                                 category=category, amount=round(amount, 2), txn_type="Debit",
                                 payment_mode=pick_payment_mode(category), merchant=merchant))

        # Occasional refund (money back from online shopping)
        if random.random() < 0.25:
            rows.append(dict(date=random_day_in_month(year, month),
                             description="Refund - Amazon Order Return",
                             category="Refund", amount=round(random.uniform(300, 2500), 2),
                             txn_type="Credit", payment_mode="UPI", merchant="Amazon"))

    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)

    # Create readable transaction IDs like TXN000001
    df.insert(0, "transaction_id", [f"TXN{i:06d}" for i in range(1, len(df) + 1)])
    return df


def make_data_dirty(df):
    """
    Deliberately introduce real-world data-quality problems.
    Each problem is something the cleaning script must detect and fix.
    """
    df = df.copy()
    n = len(df)

    # Convert columns to "object" (text) so we can store mixed formats
    df["date"] = df["date"].astype(str)
    df["amount"] = df["amount"].astype(object)

    # 1) Mixed date formats on ~15% of rows (like data merged from 2 bank exports)
    idx = np.random.choice(n, int(n * 0.15), replace=False)
    for i in idx:
        d = pd.to_datetime(df.at[i, "date"])
        df.at[i, "date"] = random.choice([d.strftime("%d/%m/%Y"), d.strftime("%d-%b-%Y")])

    # 2) Amount stored as text with rupee symbol and commas (~8%)
    idx = np.random.choice(n, int(n * 0.08), replace=False)
    for i in idx:
        df.at[i, "amount"] = f"₹{float(df.at[i, 'amount']):,.2f}"

    # 3) Inconsistent category spelling / spacing / case (~10%)
    idx = np.random.choice(n, int(n * 0.10), replace=False)
    for i in idx:
        cat = df.at[i, "category"]
        df.at[i, "category"] = random.choice([cat.upper(), cat.lower(), f" {cat} ", cat.replace("&", "and")])

    # 4) Missing category (~2%) - can be recovered using the merchant name
    idx = np.random.choice(n, int(n * 0.02), replace=False)
    df.loc[idx, "category"] = np.nan

    # 5) Missing payment mode (~3%)
    idx = np.random.choice(n, int(n * 0.03), replace=False)
    df.loc[idx, "payment_mode"] = np.nan

    # 6) Negative amounts for a few debits (sign error in export) (~1%)
    debit_rows = df.index[df["txn_type"] == "Debit"].to_numpy()
    idx = np.random.choice(debit_rows, int(n * 0.01), replace=False)
    for i in idx:
        value = df.at[i, "amount"]
        if isinstance(value, (int, float)):
            df.at[i, "amount"] = -abs(value)

    # 7) Inconsistent transaction-type labels
    idx = np.random.choice(n, int(n * 0.04), replace=False)
    df.loc[idx, "txn_type"] = df.loc[idx, "txn_type"].map({"Debit": "DR", "Credit": "CR"})

    # 8) A few extreme outliers (typing error: extra zeros) in Food & Dining
    food_rows = df.index[df["category"] == "Food & Dining"].to_numpy()
    for i in np.random.choice(food_rows, 4, replace=False):
        if isinstance(df.at[i, "amount"], (int, float)):
            df.at[i, "amount"] = float(df.at[i, "amount"]) * 100

    # 9) Exact duplicate rows (~2%) - the same transaction exported twice
    dup_idx = np.random.choice(n, int(n * 0.02), replace=False)
    df = pd.concat([df, df.loc[dup_idx]], ignore_index=True)

    # Shuffle row order (bank exports are not always sorted)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    return df


def build_budget(clean_df):
    """
    Create a monthly budget plan for every expense category.

    The budget is what the person PLANNED to spend. We base it on a sensible
    50/30/20-style plan and keep it fixed per year (people rarely revise
    budgets every month). Some categories are deliberately tight so the
    dashboard has real "over budget" alerts to show.
    """
    budget_2024 = {
        "Rent": 15000, "Groceries": 8000, "Food & Dining": 5500,
        "Transportation": 6000, "Utilities": 4500, "Shopping": 6000,
        "Entertainment": 2500, "Healthcare": 2500, "Education": 1500,
        "Travel": 4000, "Subscriptions": 1500, "Insurance": 2200,
    }
    # 2025 budget revised after the salary hike / rent increase
    budget_2025 = dict(budget_2024, Rent=15750, Groceries=8500, Shopping=7000,
                       Travel=5000, **{"Food & Dining": 6000})

    rows = []
    for year, month in month_iter(START_DATE, END_DATE):
        plan = budget_2024 if year == 2024 else budget_2025
        for category, amount in plan.items():
            # A good planner budgets the yearly health premium in March
            if category == "Insurance" and month == 3:
                amount += 18500
            rows.append({"month": f"{year}-{month:02d}", "category": category, "budget_amount": amount})
    return pd.DataFrame(rows)


def main():
    config.ensure_folders()

    clean = build_clean_transactions()
    dirty = make_data_dirty(clean)
    budget = build_budget(clean)

    dirty.to_csv(config.RAW_TRANSACTIONS_FILE, index=False)
    budget.to_csv(config.BUDGET_FILE, index=False)

    print(f"Raw transactions saved : {config.RAW_TRANSACTIONS_FILE}  ({len(dirty):,} rows)")
    print(f"Monthly budget saved   : {config.BUDGET_FILE}  ({len(budget):,} rows)")


if __name__ == "__main__":
    main()
