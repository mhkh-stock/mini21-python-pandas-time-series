# Mini #21 — findings (Noor Electronics, SAMPLE data)

Fictional Pakistani electronics store, daily sales Jan 2023 – Dec 2025
(1,096 days, 36 months).
**SAMPLE / DEMO data only** — invented store, invented sales,
never real client or real business data. Every number below is
recomputed from `data/raw/sales_daily_SAMPLE.csv` by
`src/run_techniques.py` and re-checked independently by
`src/checks.py`.

## Headline numbers

- **1,096 daily rows** worth **PKR 309,418,500**
  (25,074 units, PKR 29,546,857 ad spend).
- **Average month: PKR 8,594,958.33**;
  average day: PKR 282,316.15.
- **Revenue grew from PKR 89,142,600 (2023) to PKR 117,613,800 (2025)** —
  a CAGR of **14.86%** per year.
- **Peak month: 2025-12** at PKR 14,608,900.
  Worst month: 2023-02 at PKR 4,887,000.
- **Seasonality: December is the strongest month** (index 150.71),
  **February the weakest** (index 69.26).
- **Backtest MAPE (Oct–Dec 2025): naive 26.44%, seasonal-naive 13.14%** —
  the seasonal forecast wins.
- **Weekends beat weekdays by 15.9%** on average daily
  revenue (PKR 312,988.18 vs
  PKR 270,055.17).

## What the 10 techniques show

1. **Monthly resample (technique_01).** Daily noise collapses into
   36 clean months. 2023 totals PKR 89,142,600, 2024 totals
   PKR 102,662,100, 2025 totals PKR 117,613,800 —
   every year is bigger than the last.
2. **Rolling averages (technique_02).** The 3-month average smooths
   single-month spikes; the 12-month average is the trend line —
   it ends Dec 2025 at PKR 9,801,150, well above
   where it started (PKR 7,428,550 in Dec 2023), and it rises in
   every single month of the series — no sustained fall anywhere.
3. **Month-over-month growth (technique_03).** The biggest jump is
   2023-03 at +36.41%;
   the biggest fall is 2024-01 at
   -34.09%. The biggest moves are the
   March rebound out of the February dip and the January comedown
   after December — seasonality, not shocks.
4. **Year-over-year growth (technique_04).** Every one of the 24
   months in 2024–2025 beats the same month a year earlier. The
   strongest YoY month is 2024-02 at
   +26.29%; the weakest is
   2025-02 at +10.19% —
   growth is real in every month, never below +10% YoY.
5. **Seasonality index (technique_05).** December averages
   150.71% of a typical month and
   February only 69.26%. The index is
   the stocking rule: order heavy for November–December, light
   for February.
6. **Trend decomposition (technique_06).** The centred 12-month
   trend rises steadily from Jul 2023 to Jun 2025 with no flat
   stretch; the seasonal component repeats every year and the
   residuals are small next to the trend — the pattern is trend +
   season, not noise.
7. **CAGR (technique_07).** Revenue compounds at
   14.86% a year (2023 → 2025), which
   is 2.35% a month compounded.
   That is the single number for the "how fast are we growing"
   question.
8. **Best / worst periods (technique_08).** Best quarter:
   2025-Q4 at PKR 38,209,900.
   Worst quarter: 2023-Q1 at
   PKR 18,035,200. The top 5 months
   are all November–December months; the bottom 5 are dominated
   by early 2023 (the low base year) and the February dips.
9. **Forecast + backtest (technique_09).** Held out Oct–Dec 2025:
   naive MAPE 26.44%, seasonal-naive MAPE 13.14%.
   Seasonal-naive wins because it knows December is big. The
   Jan–Mar 2026 seasonal-naive forecasts are
   PKR 8,621,000,
   PKR 6,800,900 and
   PKR 9,182,000 — use
   those, not the flat naive number.
10. **Weekday vs weekend (technique_10).** The best day is
    Saturday at PKR 317,593
    a day; the weakest is Monday at
    PKR 263,732 a day.
    Weekends average PKR 312,988.18
    a day against PKR 270,055.17 on
    weekdays (+15.9%) — staff and stock the weekend.

## The December trap

December looks like a new level every year — 2025-12
is the peak month of the whole 3 years — and then January falls
back by roughly a third. A forecast that carries December forward
(the naive forecast) overstates January badly; the seasonal-naive
forecast, which looks at last January instead, is the honest one.
That is exactly what the backtest proves: naive MAPE 26.44%
against seasonal-naive MAPE 13.14%.

## Limits

- SAMPLE data: the store, the sales and the "findings" are
  invented to teach the techniques. The pandas patterns are real.
- One row per day, one leading category per day — the file is a
  daily total, not an order-level file, so no basket or
  per-category time series can be built from it.
- The forecasts are naive baselines, not a fitted model — they
  are the benchmark a real model (the Flagship 3 forecaster) has
  to beat, not the forecast itself.
- 36 months is short for seasonality: each calendar month is
  only observed 3 times, so the seasonality index is an estimate,
  not a law.
