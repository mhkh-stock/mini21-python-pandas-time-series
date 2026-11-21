# Mini #21 — data dictionary (SAMPLE / DEMO only)

Fictional store "Noor Electronics" — a made-up Pakistani electronics
store, daily sales 1 Jan 2023 – 31 Dec 2025 (1,096 days, 36 months).
The store, the sales and every number are invented for teaching —
the pandas techniques are real, the business is not. Regenerate
exactly with `python3 src/generate_data.py` (seed 21, deterministic).
Analyse with `python3 src/run_techniques.py`.

## data/raw/sales_daily_SAMPLE.csv (1,096 rows)

| Column | Meaning |
|---|---|
| `date` | Trading day, ISO `yyyy-mm-dd`, 2023-01-01 – 2025-12-31 (contiguous, no gaps) |
| `product_category` | That day's leading category: Mobiles, Laptops, Home Appliances, Accessories |
| `units` | Units sold that day in the leading category (≥ 1) |
| `revenue` | Revenue that day, PKR — always `units × category price` |
| `ad_spend` | Ad spend that day, PKR — 7–12% of the day's revenue |

Fixed prices: Mobiles PKR 42,000 · Laptops PKR 135,000 ·
Home Appliances PKR 18,500 · Accessories PKR 3,200.

## How the story was weighted (seed 21)

The generator is weighted so the techniques find real structure:

- **Trend growth (~1.2% a month):** 2023 totals PKR 89,142,600,
  2024 PKR 102,662,100, 2025 PKR 117,613,800 — a CAGR of 14.86%.
- **Seasonality:** December averages 150.71% of a typical month,
  November 129.37%, February only 69.26%. Peak month is 2025-12
  (PKR 14,608,900); worst month is 2023-02 (PKR 4,887,000).
- **Weekend lift:** Saturdays and Sundays average PKR 312,988 a day
  against PKR 270,055 on weekdays (+15.9%). Saturday is the best
  day (PKR 317,593 a day); Monday the weakest (PKR 263,732).
- **Daily noise:** ±9% around the trend × season × weekday target,
  so monthly aggregates are smooth but daily rows are not flat.

## Totals (verified)

- 1,096 days, 25,074 units, total revenue PKR 309,418,500.
- Average day PKR 282,316.15; average month PKR 8,594,958.33.
- Ad spend PKR 29,546,857 (9.55% of revenue).
- Every row satisfies `revenue = units × category price`
  (checked by `src/checks.py`); dates are contiguous with no gaps.

## Known quirks

- **One row per day, one leading category per day.** The file is a
  daily total, not an order-level file — no basket analysis and no
  per-category time series can be built from it. The category
  column records which category led that day's sales.
- **The story is baked in.** The weights above are the findings;
  change the weights and the findings change. That is the point
  of a teaching dataset — but it also means no finding here is
  evidence about any real store.
- **36 months is short for seasonality.** Each calendar month is
  observed only 3 times, so the seasonality index is an estimate,
  not a law — and the forecasts in technique 9 are naive baselines,
  the benchmark a real model has to beat.
