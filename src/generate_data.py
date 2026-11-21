"""Regenerate data/raw/sales_daily_SAMPLE.csv — Mini #21 sample data.

Fictional shop "Noor Electronics" — a made-up Pakistani electronics
store. One row per trading day, 1 Jan 2023 – 31 Dec 2025
(1,096 days; 2024 is a leap year). SAMPLE / DEMO data only — never
real client or real business data.

Seeded (seed 21) and fully deterministic: re-running this script
reproduces the file byte-for-byte (src/checks.py verifies that).

The generator is deliberately weighted so the techniques find real
structure (the weights below are the story, not an accident):

  * Trend growth — daily revenue grows ~1.2% a month, so 2025 is
    roughly 1.5x 2023. The CAGR technique measures exactly this.
  * Seasonality — November and December peak (winter / year-end
    shopping), February dips. The seasonality-index technique
    measures exactly this.
  * Weekend lift — Saturdays and Sundays sell more than weekdays.
    The weekday/weekend technique measures exactly this.
  * One fixed price per category, so revenue is always
    units x price (checked by src/checks.py).

Columns: date, product_category, units, revenue, ad_spend.
product_category is that day's leading category by revenue (a
weighted draw); units and revenue are that category's sales for
the day. ad_spend is 7–12% of the day's revenue.
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "raw" / "sales_daily_SAMPLE.csv"

SEED = 21
START = date(2023, 1, 1)
END = date(2025, 12, 31)  # inclusive: 1,096 days (2024 is a leap year)

# Fixed price per unit (PKR) — the same price every time a category sells.
PRICES = {
    "Mobiles": 42000,
    "Laptops": 135000,
    "Home Appliances": 18500,
    "Accessories": 3200,
}
# How often each category is the day's leading category.
CATEGORY_WEIGHTS = [("Mobiles", 0.45), ("Laptops", 0.12),
                    ("Home Appliances", 0.26), ("Accessories", 0.17)]

BASE_DAILY_REVENUE = 210000  # Jan 2023 target, before trend/seasonality
MONTHLY_TREND = 1.012        # ~1.2% growth per month

# Seasonal factor by calendar month: Nov–Dec peak, Feb dip.
SEASONAL = {1: 0.95, 2: 0.82, 3: 1.00, 4: 1.02, 5: 1.05, 6: 0.98,
            7: 0.92, 8: 0.95, 9: 1.00, 10: 1.08, 11: 1.32, 12: 1.48}
# Weekday factor (Monday=0): Saturday is the biggest trading day.
WEEKDAY = {0: 0.95, 1: 0.97, 2: 1.00, 3: 1.02, 4: 0.98, 5: 1.18, 6: 1.12}

COLUMNS = ["date", "product_category", "units", "revenue", "ad_spend"]


def weighted(rng, pairs):
    """Pick one label from [(label, weight), ...] using rng.random()."""
    roll = rng.random()
    acc = 0.0
    for label, w in pairs:
        acc += w
        if roll < acc:
            return label
    return pairs[-1][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    rng = random.Random(SEED)
    rows = []
    day = START
    while day <= END:
        months_since_start = (day.year - 2023) * 12 + (day.month - 1)
        target = (BASE_DAILY_REVENUE
                  * (MONTHLY_TREND ** months_since_start)
                  * SEASONAL[day.month]
                  * WEEKDAY[day.weekday()]
                  * rng.gauss(1.0, 0.09))
        category = weighted(rng, CATEGORY_WEIGHTS)
        price = PRICES[category]
        units = max(1, round(target / price))
        revenue = units * price
        ad_spend = round(revenue * rng.uniform(0.07, 0.12))
        rows.append({
            "date": day.isoformat(),
            "product_category": category,
            "units": units,
            "revenue": revenue,
            "ad_spend": ad_spend,
        })
        day += timedelta(days=1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    total = sum(r["revenue"] for r in rows)
    print(f"Wrote {args.out} ({len(rows)} days, "
          f"total revenue PKR {total:,})")


if __name__ == "__main__":
    main()
