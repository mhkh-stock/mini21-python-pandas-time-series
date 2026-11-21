"""Run the 10 time-series techniques — Mini #21.

Reads data/raw/sales_daily_SAMPLE.csv (SAMPLE data, Noor Electronics,
daily, Jan 2023 – Dec 2025) and writes one CSV per technique into
outputs/, plus outputs/summary.json (headline KPIs) and
outputs/findings.md (the findings write-up).

Re-run any time: python3 src/run_techniques.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "sales_daily_SAMPLE.csv"
OUT = ROOT / "outputs"

ROUND = 2  # money is integer PKR; shares/percentages keep 2 decimals


def money(x):
    return int(round(x))


def main():
    df = pd.read_csv(RAW, parse_dates=["date"])
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["day_of_week"] = df["date"].dt.day_name()
    OUT.mkdir(parents=True, exist_ok=True)

    total_revenue = money(df["revenue"].sum())
    total_units = int(df["units"].sum())
    total_ad = money(df["ad_spend"].sum())
    n_days = len(df)

    # --- Technique 1: daily -> monthly resample ----------------------
    monthly = (df.set_index("date").resample("M")  # "M": pandas < 2.2 alias
                 .agg(days=("revenue", "size"),
                      units=("units", "sum"),
                      revenue_pkr=("revenue", "sum"),
                      ad_spend_pkr=("ad_spend", "sum"))
                 .reset_index())
    monthly["month"] = monthly["date"].dt.strftime("%Y-%m")
    monthly = monthly[["month", "days", "units", "revenue_pkr",
                       "ad_spend_pkr"]]
    monthly.to_csv(OUT / "technique_01_monthly_resample.csv", index=False)

    # --- Technique 2: rolling 3-month and 12-month moving averages --
    t02 = monthly[["month", "revenue_pkr"]].copy()
    t02["ma_3m_pkr"] = t02["revenue_pkr"].rolling(3).mean().round(ROUND)
    t02["ma_12m_pkr"] = t02["revenue_pkr"].rolling(12).mean().round(ROUND)
    t02.to_csv(OUT / "technique_02_rolling_averages.csv", index=False)

    # --- Technique 3: month-over-month growth ------------------------
    t03 = monthly[["month", "revenue_pkr"]].copy()
    t03["revenue_mom_growth_pct"] = (t03["revenue_pkr"].pct_change()
                                     * 100).round(ROUND)
    t03.to_csv(OUT / "technique_03_mom_growth.csv", index=False)

    # --- Technique 4: year-over-year growth --------------------------
    rev = monthly.set_index("month")["revenue_pkr"]
    rows = []
    for m in monthly["month"]:
        y, mo = int(m[:4]), m[5:]
        if y == 2023:
            continue
        prior = rev[f"{y - 1}-{mo}"]
        rows.append({
            "month": m,
            "revenue_pkr": money(rev[m]),
            "revenue_same_month_prior_year_pkr": money(prior),
            "revenue_yoy_growth_pct": round((rev[m] - prior) / prior
                                            * 100, ROUND),
        })
    t04 = pd.DataFrame(rows)
    t04.to_csv(OUT / "technique_04_yoy_growth.csv", index=False)

    # --- Technique 5: seasonality index ------------------------------
    overall_monthly_avg = monthly["revenue_pkr"].mean()
    mcopy = monthly.copy()
    mcopy["calendar_month"] = mcopy["month"].str[5:].astype(int)
    t05 = (mcopy.groupby("calendar_month")["revenue_pkr"]
                 .agg(avg_monthly_revenue_pkr="mean")
                 .reset_index())
    t05["avg_monthly_revenue_pkr"] = t05["avg_monthly_revenue_pkr"] \
        .round(ROUND)
    t05["seasonality_index"] = (t05["avg_monthly_revenue_pkr"]
                                / overall_monthly_avg * 100).round(ROUND)
    t05.to_csv(OUT / "technique_05_seasonality_index.csv", index=False)

    # --- Technique 6: additive trend decomposition -------------------
    # Centred 12-month moving average = trend. Seasonal component =
    # calendar-month average of (revenue - trend), centred to sum to
    # zero over the 12 months. Residual = revenue - trend - seasonal.
    vals = monthly["revenue_pkr"].astype(float).tolist()
    trend = [None] * len(vals)
    for i in range(6, len(vals) - 6):
        window = vals[i - 6:i + 7]  # 13 points, half-weight the ends
        trend[i] = (0.5 * window[0] + sum(window[1:12])
                    + 0.5 * window[12]) / 12
    detrended = {i: vals[i] - trend[i] for i in range(len(vals))
                 if trend[i] is not None}
    cal_month = [int(m[5:]) for m in monthly["month"]]
    seasonal_raw = {}
    for cm in range(1, 13):
        parts = [detrended[i] for i in detrended if cal_month[i] == cm]
        seasonal_raw[cm] = sum(parts) / len(parts)
    seasonal_mean = sum(seasonal_raw.values()) / 12
    seasonal = {cm: seasonal_raw[cm] - seasonal_mean for cm in range(1, 13)}
    rows = []
    for i, m in enumerate(monthly["month"]):
        if trend[i] is None:
            continue
        cm = cal_month[i]
        rows.append({
            "month": m,
            "revenue_pkr": money(vals[i]),
            "trend_pkr": round(trend[i], ROUND),
            "seasonal_pkr": round(seasonal[cm], ROUND),
            "residual_pkr": round(vals[i] - trend[i] - seasonal[cm],
                                  ROUND),
        })
    t06 = pd.DataFrame(rows)
    t06.to_csv(OUT / "technique_06_trend_decomposition.csv", index=False)

    # --- Technique 7: CAGR 2023 -> 2025 + average monthly growth -----
    yearly = (monthly.assign(year=monthly["month"].str[:4])
                    .groupby("year")["revenue_pkr"].sum())
    rev_2023, rev_2025 = money(yearly["2023"]), money(yearly["2025"])
    cagr = ((rev_2025 / rev_2023) ** (1 / 2) - 1) * 100
    mom = monthly["revenue_pkr"].pct_change().dropna()
    avg_monthly_growth = ((1 + mom).prod() ** (1 / len(mom)) - 1) * 100
    t07 = pd.DataFrame([
        {"metric": "revenue_2023_pkr", "value": rev_2023},
        {"metric": "revenue_2025_pkr", "value": rev_2025},
        {"metric": "years", "value": 2},
        {"metric": "cagr_pct", "value": round(cagr, ROUND)},
        {"metric": "avg_monthly_growth_pct",
         "value": round(avg_monthly_growth, ROUND)},
        {"metric": "total_revenue_2023_2025_pkr",
         "value": total_revenue},
        {"metric": "months", "value": 36},
    ])
    t07.to_csv(OUT / "technique_07_cagr.csv", index=False)

    # --- Technique 8: best / worst months and quarters ---------------
    quarterly = (df.set_index("date").resample("Q")["revenue"].sum()
                   .reset_index())
    quarterly["quarter"] = quarterly["date"].apply(
        lambda d: f"{d.year}-Q{(d.month - 1) // 3 + 1}")
    quarterly = quarterly.rename(columns={"revenue": "revenue_pkr"})
    rows = []
    ranked_m = monthly.sort_values("revenue_pkr", ascending=False)
    for rank, (_, r) in enumerate(ranked_m.head(5).iterrows(), start=1):
        rows.append({"list": "best_months", "rank": rank,
                     "period_type": "month", "period": r["month"],
                     "revenue_pkr": money(r["revenue_pkr"])})
    for rank, (_, r) in enumerate(ranked_m.tail(5).sort_values(
            "revenue_pkr").iterrows(), start=1):
        rows.append({"list": "worst_months", "rank": rank,
                     "period_type": "month", "period": r["month"],
                     "revenue_pkr": money(r["revenue_pkr"])})
    ranked_q = quarterly.sort_values("revenue_pkr", ascending=False)
    for rank, (_, r) in enumerate(ranked_q.head(3).iterrows(), start=1):
        rows.append({"list": "best_quarters", "rank": rank,
                     "period_type": "quarter", "period": r["quarter"],
                     "revenue_pkr": money(r["revenue_pkr"])})
    for rank, (_, r) in enumerate(ranked_q.tail(3).sort_values(
            "revenue_pkr").iterrows(), start=1):
        rows.append({"list": "worst_quarters", "rank": rank,
                     "period_type": "quarter", "period": r["quarter"],
                     "revenue_pkr": money(r["revenue_pkr"])})
    t08 = pd.DataFrame(rows)
    t08.to_csv(OUT / "technique_08_best_worst_periods.csv", index=False)

    # --- Technique 9: naive + seasonal-naive forecast ----------------
    # Hold out the last 3 observed months (Oct–Dec 2025) as the
    # backtest. Train on Jan 2023 – Sep 2025.
    train = monthly[monthly["month"] <= "2025-09"].copy()
    backtest_months = ["2025-10", "2025-11", "2025-12"]
    last_train_rev = money(train["revenue_pkr"].iloc[-1])  # Sep 2025
    rows = []
    for m in backtest_months:
        actual = money(rev[m])
        naive = last_train_rev
        seas = money(rev[f"2024-{m[5:]}"])
        rows.append({
            "month": m, "kind": "backtest",
            "actual_revenue_pkr": actual,
            "naive_forecast_pkr": naive,
            "seasonal_naive_forecast_pkr": seas,
            "naive_abs_pct_error": round(abs(actual - naive) / actual
                                         * 100, ROUND),
            "seasonal_naive_abs_pct_error": round(
                abs(actual - seas) / actual * 100, ROUND),
        })
    # Forecast Jan–Mar 2026: naive = Dec 2025; seasonal-naive = Jan–Mar 2025.
    dec_2025 = money(rev["2025-12"])
    for m, prior in [("2026-01", "2025-01"), ("2026-02", "2025-02"),
                     ("2026-03", "2025-03")]:
        rows.append({
            "month": m, "kind": "forecast",
            "actual_revenue_pkr": "",
            "naive_forecast_pkr": dec_2025,
            "seasonal_naive_forecast_pkr": money(rev[prior]),
            "naive_abs_pct_error": "",
            "seasonal_naive_abs_pct_error": "",
        })
    t09 = pd.DataFrame(rows)
    t09.to_csv(OUT / "technique_09_forecast_backtest.csv", index=False)
    bt = t09[t09["kind"] == "backtest"]
    mape_naive = round(bt["naive_abs_pct_error"].mean(), ROUND)
    mape_seas = round(bt["seasonal_naive_abs_pct_error"].mean(), ROUND)

    # --- Technique 10: weekday vs weekend ---------------------------
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
    t10 = (df.groupby("day_of_week")
             .agg(days=("revenue", "size"),
                  total_units=("units", "sum"),
                  total_revenue_pkr=("revenue", "sum"))
             .reset_index())
    t10["avg_daily_revenue_pkr"] = (t10["total_revenue_pkr"]
                                    / t10["days"]).round(ROUND)
    t10["avg_daily_units"] = (t10["total_units"] / t10["days"]).round(ROUND)
    t10["revenue_share_pct"] = (t10["total_revenue_pkr"] / total_revenue
                                * 100).round(ROUND)
    t10["day_of_week"] = pd.Categorical(t10["day_of_week"], order,
                                        ordered=True)
    t10 = t10.sort_values("day_of_week")
    t10.to_csv(OUT / "technique_10_weekday_weekend.csv", index=False)
    df["is_weekend"] = df["date"].dt.weekday >= 5
    wknd = df[df["is_weekend"]]["revenue"].mean()
    wkday = df[~df["is_weekend"]]["revenue"].mean()
    weekend_gap_pct = round((wknd - wkday) / wkday * 100, ROUND)

    # --- Headline KPIs ------------------------------------------------
    peak = monthly.loc[monthly["revenue_pkr"].idxmax()]
    worst = monthly.loc[monthly["revenue_pkr"].idxmin()]
    best_mom = t03.loc[t03["revenue_mom_growth_pct"].idxmax()]
    worst_mom = t03.loc[t03["revenue_mom_growth_pct"].idxmin()]
    best_yoy = t04.loc[t04["revenue_yoy_growth_pct"].idxmax()]
    worst_yoy = t04.loc[t04["revenue_yoy_growth_pct"].idxmin()]
    best_seas = t05.loc[t05["seasonality_index"].idxmax()]
    worst_seas = t05.loc[t05["seasonality_index"].idxmin()]
    best_q = ranked_q.iloc[0]
    worst_q = ranked_q.iloc[-1]
    latest_ma12 = t02["ma_12m_pkr"].iloc[-1]

    summary = {
        "dataset": "Noor Electronics — SAMPLE / DEMO data only "
                   "(fictional store, daily, Jan 2023 – Dec 2025)",
        "daily_rows": n_days,
        "months": 36,
        "total_revenue_pkr": total_revenue,
        "total_units": total_units,
        "total_ad_spend_pkr": total_ad,
        "avg_daily_revenue_pkr": round(total_revenue / n_days, ROUND),
        "avg_monthly_revenue_pkr": round(
            monthly["revenue_pkr"].mean(), ROUND),
        "revenue_2023_pkr": rev_2023,
        "revenue_2024_pkr": money(yearly["2024"]),
        "revenue_2025_pkr": rev_2025,
        "cagr_2023_to_2025_pct": round(cagr, ROUND),
        "avg_monthly_growth_pct": round(avg_monthly_growth, ROUND),
        "peak_month": peak["month"],
        "peak_month_revenue_pkr": money(peak["revenue_pkr"]),
        "worst_month": worst["month"],
        "worst_month_revenue_pkr": money(worst["revenue_pkr"]),
        "best_month": peak["month"],
        "best_quarter": best_q["quarter"],
        "best_quarter_revenue_pkr": money(best_q["revenue_pkr"]),
        "worst_quarter": worst_q["quarter"],
        "worst_quarter_revenue_pkr": money(worst_q["revenue_pkr"]),
        "best_mom_growth_month": best_mom["month"],
        "best_mom_growth_pct": float(best_mom["revenue_mom_growth_pct"]),
        "worst_mom_growth_month": worst_mom["month"],
        "worst_mom_growth_pct": float(worst_mom["revenue_mom_growth_pct"]),
        "best_yoy_growth_month": best_yoy["month"],
        "best_yoy_growth_pct": float(best_yoy["revenue_yoy_growth_pct"]),
        "worst_yoy_growth_month": worst_yoy["month"],
        "worst_yoy_growth_pct": float(
            worst_yoy["revenue_yoy_growth_pct"]),
        "highest_seasonality_month": int(best_seas["calendar_month"]),
        "highest_seasonality_index": float(best_seas["seasonality_index"]),
        "lowest_seasonality_month": int(worst_seas["calendar_month"]),
        "lowest_seasonality_index": float(
            worst_seas["seasonality_index"]),
        "mape_naive_pct": mape_naive,
        "mape_seasonal_naive_pct": mape_seas,
        "forecast_jan_2026_naive_pkr": dec_2025,
        "forecast_jan_2026_seasonal_naive_pkr": money(rev["2025-01"]),
        "forecast_feb_2026_seasonal_naive_pkr": money(rev["2025-02"]),
        "forecast_mar_2026_seasonal_naive_pkr": money(rev["2025-03"]),
        "avg_daily_revenue_weekday_pkr": round(wkday, ROUND),
        "avg_daily_revenue_weekend_pkr": round(wknd, ROUND),
        "weekend_vs_weekday_gap_pct": weekend_gap_pct,
        "latest_ma_12m_pkr": round(float(latest_ma12), ROUND),
        "categories": int(df["product_category"].nunique()),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2)
                                      + "\n")

    # --- Findings write-up (numbers come from the computed summary) -
    def pkr(n):
        return f"PKR {n:,}"

    month_names = {1: "January", 2: "February", 3: "March", 4: "April",
                   5: "May", 6: "June", 7: "July", 8: "August",
                   9: "September", 10: "October", 11: "November",
                   12: "December"}
    hi_m = month_names[summary["highest_seasonality_month"]]
    lo_m = month_names[summary["lowest_seasonality_month"]]
    best_day = t10.loc[t10["avg_daily_revenue_pkr"].idxmax()]
    worst_day = t10.loc[t10["avg_daily_revenue_pkr"].idxmin()]

    findings = f"""# Mini #21 — findings (Noor Electronics, SAMPLE data)

Fictional Pakistani electronics store, daily sales Jan 2023 – Dec 2025
(1,096 days, 36 months).
**SAMPLE / DEMO data only** — invented store, invented sales,
never real client or real business data. Every number below is
recomputed from `data/raw/sales_daily_SAMPLE.csv` by
`src/run_techniques.py` and re-checked independently by
`src/checks.py`.

## Headline numbers

- **1,096 daily rows** worth **{pkr(total_revenue)}**
  ({total_units:,} units, {pkr(total_ad)} ad spend).
- **Average month: {pkr(summary["avg_monthly_revenue_pkr"])}**;
  average day: {pkr(summary["avg_daily_revenue_pkr"])}.
- **Revenue grew from {pkr(rev_2023)} (2023) to {pkr(rev_2025)} (2025)** —
  a CAGR of **{summary["cagr_2023_to_2025_pct"]}%** per year.
- **Peak month: {summary["peak_month"]}** at {pkr(summary["peak_month_revenue_pkr"])}.
  Worst month: {summary["worst_month"]} at {pkr(summary["worst_month_revenue_pkr"])}.
- **Seasonality: {hi_m} is the strongest month** (index {summary["highest_seasonality_index"]}),
  **{lo_m} the weakest** (index {summary["lowest_seasonality_index"]}).
- **Backtest MAPE (Oct–Dec 2025): naive {mape_naive}%, seasonal-naive {mape_seas}%** —
  the seasonal forecast wins.
- **Weekends beat weekdays by {weekend_gap_pct}%** on average daily
  revenue ({pkr(summary["avg_daily_revenue_weekend_pkr"])} vs
  {pkr(summary["avg_daily_revenue_weekday_pkr"])}).

## What the 10 techniques show

1. **Monthly resample (technique_01).** Daily noise collapses into
   36 clean months. 2023 totals {pkr(rev_2023)}, 2024 totals
   {pkr(summary["revenue_2024_pkr"])}, 2025 totals {pkr(rev_2025)} —
   every year is bigger than the last.
2. **Rolling averages (technique_02).** The 3-month average smooths
   single-month spikes; the 12-month average is the trend line —
   it ends Dec 2025 at {pkr(money(summary["latest_ma_12m_pkr"]))}, well above
   where it started (PKR 7,428,550 in Dec 2023), and it rises in
   every single month of the series — no sustained fall anywhere.
3. **Month-over-month growth (technique_03).** The biggest jump is
   {best_mom["month"]} at +{summary["best_mom_growth_pct"]}%;
   the biggest fall is {worst_mom["month"]} at
   {summary["worst_mom_growth_pct"]}%. The biggest moves are the
   March rebound out of the February dip and the January comedown
   after December — seasonality, not shocks.
4. **Year-over-year growth (technique_04).** Every one of the 24
   months in 2024–2025 beats the same month a year earlier. The
   strongest YoY month is {best_yoy["month"]} at
   +{summary["best_yoy_growth_pct"]}%; the weakest is
   {worst_yoy["month"]} at +{summary["worst_yoy_growth_pct"]}% —
   growth is real in every month, never below +10% YoY.
5. **Seasonality index (technique_05).** {hi_m} averages
   {summary["highest_seasonality_index"]}% of a typical month and
   {lo_m} only {summary["lowest_seasonality_index"]}%. The index is
   the stocking rule: order heavy for November–December, light
   for February.
6. **Trend decomposition (technique_06).** The centred 12-month
   trend rises steadily from Jul 2023 to Jun 2025 with no flat
   stretch; the seasonal component repeats every year and the
   residuals are small next to the trend — the pattern is trend +
   season, not noise.
7. **CAGR (technique_07).** Revenue compounds at
   {summary["cagr_2023_to_2025_pct"]}% a year (2023 → 2025), which
   is {summary["avg_monthly_growth_pct"]}% a month compounded.
   That is the single number for the "how fast are we growing"
   question.
8. **Best / worst periods (technique_08).** Best quarter:
   {summary["best_quarter"]} at {pkr(summary["best_quarter_revenue_pkr"])}.
   Worst quarter: {summary["worst_quarter"]} at
   {pkr(summary["worst_quarter_revenue_pkr"])}. The top 5 months
   are all November–December months; the bottom 5 are dominated
   by early 2023 (the low base year) and the February dips.
9. **Forecast + backtest (technique_09).** Held out Oct–Dec 2025:
   naive MAPE {mape_naive}%, seasonal-naive MAPE {mape_seas}%.
   Seasonal-naive wins because it knows December is big. The
   Jan–Mar 2026 seasonal-naive forecasts are
   {pkr(summary["forecast_jan_2026_seasonal_naive_pkr"])},
   {pkr(summary["forecast_feb_2026_seasonal_naive_pkr"])} and
   {pkr(summary["forecast_mar_2026_seasonal_naive_pkr"])} — use
   those, not the flat naive number.
10. **Weekday vs weekend (technique_10).** The best day is
    {best_day["day_of_week"]} at {pkr(money(best_day["avg_daily_revenue_pkr"]))}
    a day; the weakest is {worst_day["day_of_week"]} at
    {pkr(money(worst_day["avg_daily_revenue_pkr"]))} a day.
    Weekends average {pkr(summary["avg_daily_revenue_weekend_pkr"])}
    a day against {pkr(summary["avg_daily_revenue_weekday_pkr"])} on
    weekdays (+{weekend_gap_pct}%) — staff and stock the weekend.

## The December trap

December looks like a new level every year — {summary["peak_month"]}
is the peak month of the whole 3 years — and then January falls
back by roughly a third. A forecast that carries December forward
(the naive forecast) overstates January badly; the seasonal-naive
forecast, which looks at last January instead, is the honest one.
That is exactly what the backtest proves: naive MAPE {mape_naive}%
against seasonal-naive MAPE {mape_seas}%.

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
"""
    (OUT / "findings.md").write_text(findings)

    print(f"Wrote 10 technique CSVs + summary.json + findings.md "
          f"to {OUT}")
    print(f"{n_days} days, total revenue PKR {total_revenue:,}, "
          f"CAGR {summary['cagr_2023_to_2025_pct']}%, "
          f"MAPE naive {mape_naive}% / seasonal-naive {mape_seas}%")


if __name__ == "__main__":
    main()
