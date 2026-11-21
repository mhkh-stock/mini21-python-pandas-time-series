"""Independent checks for Mini #21 — Time Series & Resampling Pack.

Recomputes EVERY headline number from data/raw/sales_daily_SAMPLE.csv
with the standard library only (no pandas), then compares against
every output file, outputs/summary.json, outputs/findings.md and
README.md. Also verifies the generator is deterministic by re-running
it to a temp file and byte-comparing, and that the chart PNG is a
real PNG whose source data matches the monthly CSV.

Run: python3 src/checks.py
Exit code 0 = all checks pass. Any failure is a build bug — fix the
build, never weaken the check.
"""

import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "sales_daily_SAMPLE.csv"
OUT = ROOT / "outputs"

EXPECTED_COLUMNS = ["date", "product_category", "units", "revenue",
                    "ad_spend"]
PRICES = {"Mobiles": 42000, "Laptops": 135000,
          "Home Appliances": 18500, "Accessories": 3200}
EXPECTED_CATEGORIES = set(PRICES)
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]

PASSED = 0
FAILED = []


def check(name, ok, detail=""):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def close(a, b, tol=0.01):
    return abs(a - b) <= tol


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fnum(s):
    """Float or None for a blank CSV cell."""
    return None if s in ("", None) else float(s)


def main():
    # ---------- files exist ----------
    needed = [RAW, OUT / "summary.json", OUT / "findings.md",
              OUT / "monthly_revenue_trend.png",
              ROOT / "README.md", ROOT / "data" / "README.md",
              ROOT / "requirements.txt", ROOT / ".gitignore",
              ROOT / "src" / "generate_data.py",
              ROOT / "src" / "run_techniques.py",
              ROOT / "src" / "build_chart.py",
              ROOT / "src" / "checks.py"] + [
        OUT / f"technique_{i:02d}_{slug}.csv" for i, slug in enumerate([
            "monthly_resample", "rolling_averages", "mom_growth",
            "yoy_growth", "seasonality_index", "trend_decomposition",
            "cagr", "best_worst_periods", "forecast_backtest",
            "weekday_weekend"], start=1)]
    for p in needed:
        check(f"exists {p.name}", p.is_file(), "missing file")

    # chart is a real PNG
    png = (OUT / "monthly_revenue_trend.png").read_bytes()
    check("chart is a PNG", png[:8] == b"\x89PNG\r\n\x1a\n")
    check("chart non-trivial size", len(png) > 10000,
          f"{len(png)} bytes")

    # ---------- raw file: shape and hygiene ----------
    with open(RAW, newline="") as f:
        header = next(csv.reader(f))
    check("raw header exact", header == EXPECTED_COLUMNS,
          f"got {header}")
    rows = read_csv(RAW)
    check("raw row count 1096", len(rows) == 1096, f"got {len(rows)}")
    check("no empty cells", all(v not in ("", None) for r in rows
                                for v in r.values()))
    dates = [date.fromisoformat(r["date"]) for r in rows]
    check("dates sorted ascending", dates == sorted(dates))
    check("dates contiguous 2023-01-01..2025-12-31",
          dates[0] == date(2023, 1, 1)
          and dates[-1] == date(2025, 12, 31)
          and all(dates[i + 1] - dates[i] == timedelta(days=1)
                  for i in range(len(dates) - 1)))
    check("dates unique", len(set(dates)) == len(dates))
    check("categories exactly the 4 expected",
          {r["product_category"] for r in rows} == EXPECTED_CATEGORIES)
    check("revenue == units x category price",
          all(int(r["revenue"]) == int(r["units"]) * PRICES[r["product_category"]]
              for r in rows))
    check("units >= 1", all(int(r["units"]) >= 1 for r in rows))
    check("ad_spend 7–12% of revenue",
          all(0.07 <= int(r["ad_spend"]) / int(r["revenue"]) <= 0.12
              for r in rows))
    check("all values non-negative",
          all(int(r[k]) >= 0 for r in rows for k in ("units", "revenue",
                                                      "ad_spend")))

    # ---------- independent aggregates from the raw file ----------
    grand = sum(int(r["revenue"]) for r in rows)
    total_units = sum(int(r["units"]) for r in rows)
    total_ad = sum(int(r["ad_spend"]) for r in rows)

    def month_key(d):
        return d.strftime("%Y-%m")

    by_month = defaultdict(lambda: {"days": 0, "units": 0, "revenue": 0,
                                    "ad_spend": 0})
    for r, d in zip(rows, dates):
        m = by_month[month_key(d)]
        m["days"] += 1
        m["units"] += int(r["units"])
        m["revenue"] += int(r["revenue"])
        m["ad_spend"] += int(r["ad_spend"])
    months = sorted(by_month)
    check("36 months", len(months) == 36, f"got {len(months)}")
    check("monthly revenue sums to grand",
          sum(by_month[m]["revenue"] for m in months) == grand)
    # days per month match the real calendar
    for m in months:
        y, mo = int(m[:4]), int(m[5:])
        first = date(y, mo, 1)
        nxt = date(y + 1, 1, 1) if mo == 12 else date(y, mo + 1, 1)
        check(f"days in {m}", by_month[m]["days"] == (nxt - first).days)

    monthly_rev = [by_month[m]["revenue"] for m in months]
    summary = json.loads((OUT / "summary.json").read_text())

    # ---------- summary.json headlines ----------
    check("summary daily_rows", summary["daily_rows"] == 1096)
    check("summary total_revenue",
          summary["total_revenue_pkr"] == grand, f"{summary['total_revenue_pkr']} vs {grand}")
    check("summary total_units", summary["total_units"] == total_units)
    check("summary total_ad_spend",
          summary["total_ad_spend_pkr"] == total_ad)
    check("summary avg_daily_revenue",
          close(summary["avg_daily_revenue_pkr"], grand / 1096))
    check("summary avg_monthly_revenue",
          close(summary["avg_monthly_revenue_pkr"], grand / 36))
    yearly = defaultdict(int)
    for m in months:
        yearly[m[:4]] += by_month[m]["revenue"]
    check("summary revenue_2023",
          summary["revenue_2023_pkr"] == yearly["2023"])
    check("summary revenue_2024",
          summary["revenue_2024_pkr"] == yearly["2024"])
    check("summary revenue_2025",
          summary["revenue_2025_pkr"] == yearly["2025"])
    cagr = ((yearly["2025"] / yearly["2023"]) ** 0.5 - 1) * 100
    check("summary CAGR", close(summary["cagr_2023_to_2025_pct"], cagr),
          f"{summary['cagr_2023_to_2025_pct']} vs {cagr:.2f}")
    mom = [(monthly_rev[i] - monthly_rev[i - 1]) / monthly_rev[i - 1]
           for i in range(1, 36)]
    geo = (math.prod(1 + x for x in mom) ** (1 / len(mom)) - 1) * 100
    check("summary avg monthly growth (geometric)",
          close(summary["avg_monthly_growth_pct"], geo),
          f"{summary['avg_monthly_growth_pct']} vs {geo:.2f}")
    peak_m = max(months, key=lambda m: by_month[m]["revenue"])
    worst_m = min(months, key=lambda m: by_month[m]["revenue"])
    check("summary peak_month", summary["peak_month"] == peak_m)
    check("summary peak revenue",
          summary["peak_month_revenue_pkr"] == by_month[peak_m]["revenue"])
    check("summary worst_month", summary["worst_month"] == worst_m)
    check("summary worst revenue",
          summary["worst_month_revenue_pkr"]
          == by_month[worst_m]["revenue"])
    best_mom_i = max(range(1, 36),
                     key=lambda i: (monthly_rev[i] - monthly_rev[i - 1])
                     / monthly_rev[i - 1])
    worst_mom_i = min(range(1, 36),
                      key=lambda i: (monthly_rev[i] - monthly_rev[i - 1])
                      / monthly_rev[i - 1])
    check("summary best MoM month",
          summary["best_mom_growth_month"] == months[best_mom_i])
    check("summary best MoM pct",
          close(summary["best_mom_growth_pct"],
                (monthly_rev[best_mom_i] - monthly_rev[best_mom_i - 1])
                / monthly_rev[best_mom_i - 1] * 100))
    check("summary worst MoM month",
          summary["worst_mom_growth_month"] == months[worst_mom_i])
    check("summary worst MoM pct",
          close(summary["worst_mom_growth_pct"],
                (monthly_rev[worst_mom_i] - monthly_rev[worst_mom_i - 1])
                / monthly_rev[worst_mom_i - 1] * 100))
    # YoY extremes
    yoy = {}
    for i, m in enumerate(months):
        if m[:4] != "2023":
            prior = by_month[f"{int(m[:4]) - 1}-{m[5:]}"]["revenue"]
            yoy[m] = (by_month[m]["revenue"] - prior) / prior * 100
    check("summary best YoY month",
          summary["best_yoy_growth_month"] == max(yoy, key=yoy.get))
    check("summary best YoY pct",
          close(summary["best_yoy_growth_pct"], max(yoy.values())))
    check("summary worst YoY month",
          summary["worst_yoy_growth_month"] == min(yoy, key=yoy.get))
    check("summary worst YoY pct",
          close(summary["worst_yoy_growth_pct"], min(yoy.values())))
    check("all 24 YoY values positive", all(v > 0 for v in yoy.values()))
    # seasonality extremes
    overall_avg = grand / 36
    cal_avg = {}
    for cm in range(1, 13):
        vals = [by_month[m]["revenue"] for m in months
                if int(m[5:]) == cm]
        cal_avg[cm] = sum(vals) / len(vals)
    hi_cm = max(cal_avg, key=cal_avg.get)
    lo_cm = min(cal_avg, key=cal_avg.get)
    check("summary highest seasonality month",
          summary["highest_seasonality_month"] == hi_cm)
    check("summary highest seasonality index",
          close(summary["highest_seasonality_index"],
                cal_avg[hi_cm] / overall_avg * 100))
    check("summary lowest seasonality month",
          summary["lowest_seasonality_month"] == lo_cm)
    check("summary lowest seasonality index",
          close(summary["lowest_seasonality_index"],
                cal_avg[lo_cm] / overall_avg * 100))
    # quarters
    by_quarter = defaultdict(int)
    for m in months:
        q = (int(m[5:]) - 1) // 3 + 1
        by_quarter[f"{m[:4]}-Q{q}"] += by_month[m]["revenue"]
    best_q = max(by_quarter, key=by_quarter.get)
    worst_q = min(by_quarter, key=by_quarter.get)
    check("summary best quarter", summary["best_quarter"] == best_q)
    check("summary best quarter revenue",
          summary["best_quarter_revenue_pkr"] == by_quarter[best_q])
    check("summary worst quarter", summary["worst_quarter"] == worst_q)
    check("summary worst quarter revenue",
          summary["worst_quarter_revenue_pkr"] == by_quarter[worst_q])

    # ---------- technique_01: monthly resample ----------
    t01 = read_csv(OUT / "technique_01_monthly_resample.csv")
    check("t01 row count 36", len(t01) == 36)
    for r in t01:
        m = r["month"]
        check(f"t01 {m} days", int(r["days"]) == by_month[m]["days"])
        check(f"t01 {m} units", int(r["units"]) == by_month[m]["units"])
        check(f"t01 {m} revenue",
              int(r["revenue_pkr"]) == by_month[m]["revenue"])
        check(f"t01 {m} ad_spend",
              int(r["ad_spend_pkr"]) == by_month[m]["ad_spend"])
    check("t01 revenue sums to grand",
          sum(int(r["revenue_pkr"]) for r in t01) == grand)

    # ---------- technique_02: rolling averages ----------
    t02 = read_csv(OUT / "technique_02_rolling_averages.csv")
    check("t02 row count 36", len(t02) == 36)
    for i, r in enumerate(t02):
        check(f"t02 {r['month']} revenue",
              int(r["revenue_pkr"]) == monthly_rev[i])
        if i >= 2:
            expect = sum(monthly_rev[i - 2:i + 1]) / 3
            check(f"t02 {r['month']} MA3",
                  close(fnum(r["ma_3m_pkr"]), expect))
        else:
            check(f"t02 {r['month']} MA3 blank",
                  fnum(r["ma_3m_pkr"]) is None)
        if i >= 11:
            expect = sum(monthly_rev[i - 11:i + 1]) / 12
            check(f"t02 {r['month']} MA12",
                  close(fnum(r["ma_12m_pkr"]), expect))
        else:
            check(f"t02 {r['month']} MA12 blank",
                  fnum(r["ma_12m_pkr"]) is None)
    check("summary latest MA12",
          close(summary["latest_ma_12m_pkr"],
                sum(monthly_rev[-12:]) / 12))
    ma12 = [sum(monthly_rev[i - 11:i + 1]) / 12 for i in range(11, 36)]
    check("MA12 rises every month",
          all(ma12[i] > ma12[i - 1] for i in range(1, len(ma12))))

    # ---------- technique_03: MoM growth ----------
    t03 = read_csv(OUT / "technique_03_mom_growth.csv")
    check("t03 row count 36", len(t03) == 36)
    for i, r in enumerate(t03):
        if i == 0:
            check("t03 first MoM blank",
                  fnum(r["revenue_mom_growth_pct"]) is None)
        else:
            expect = (monthly_rev[i] - monthly_rev[i - 1]) \
                / monthly_rev[i - 1] * 100
            check(f"t03 {r['month']} MoM",
                  close(fnum(r["revenue_mom_growth_pct"]), expect))

    # ---------- technique_04: YoY growth ----------
    t04 = read_csv(OUT / "technique_04_yoy_growth.csv")
    check("t04 row count 24", len(t04) == 24)
    for r in t04:
        m = r["month"]
        prior = by_month[f"{int(m[:4]) - 1}-{m[5:]}"]["revenue"]
        check(f"t04 {m} prior year",
              int(r["revenue_same_month_prior_year_pkr"]) == prior)
        check(f"t04 {m} YoY",
              close(float(r["revenue_yoy_growth_pct"]),
                    (by_month[m]["revenue"] - prior) / prior * 100))

    # ---------- technique_05: seasonality index ----------
    t05 = read_csv(OUT / "technique_05_seasonality_index.csv")
    check("t05 row count 12", len(t05) == 12)
    for r in t05:
        cm = int(r["calendar_month"])
        check(f"t05 month {cm} avg",
              close(float(r["avg_monthly_revenue_pkr"]), cal_avg[cm]))
        check(f"t05 month {cm} index",
              close(float(r["seasonality_index"]),
                    cal_avg[cm] / overall_avg * 100))
    idx = [float(r["seasonality_index"]) for r in t05]
    check("t05 indices average 100.0", close(sum(idx) / 12, 100.0, 0.05),
          f"mean {sum(idx) / 12:.2f}")

    # ---------- technique_06: decomposition ----------
    t06 = read_csv(OUT / "technique_06_trend_decomposition.csv")
    check("t06 row count 24 (Jul 2023–Jun 2025)", len(t06) == 24,
          f"got {len(t06)}")
    check("t06 first month 2023-07", t06[0]["month"] == "2023-07")
    check("t06 last month 2025-06", t06[-1]["month"] == "2025-06")
    # recompute centred trend + seasonal from scratch
    trend = {}
    for i in range(6, 30):
        w = monthly_rev[i - 6:i + 7]
        trend[months[i]] = (0.5 * w[0] + sum(w[1:12]) + 0.5 * w[12]) / 12
    detr = {m: by_month[m]["revenue"] - trend[m] for m in trend}
    seas_raw = {}
    for cm in range(1, 13):
        parts = [detr[m] for m in detr if int(m[5:]) == cm]
        seas_raw[cm] = sum(parts) / len(parts)
    seas_mean = sum(seas_raw.values()) / 12
    seas = {cm: seas_raw[cm] - seas_mean for cm in range(1, 13)}
    check("t06 seasonal components sum to ~0",
          close(sum(seas.values()), 0.0, 0.01))
    for r in t06:
        m = r["month"]
        check(f"t06 {m} trend",
              close(float(r["trend_pkr"]), trend[m], 0.02))
        check(f"t06 {m} seasonal",
              close(float(r["seasonal_pkr"]), seas[int(m[5:])], 0.02))
        check(f"t06 {m} components sum to revenue",
              close(float(r["trend_pkr"]) + float(r["seasonal_pkr"])
                    + float(r["residual_pkr"]),
                    by_month[m]["revenue"], 0.05))
    trends = [float(r["trend_pkr"]) for r in t06]
    check("t06 trend rises overall",
          trends[-1] > trends[0])

    # ---------- technique_07: CAGR ----------
    t07 = read_csv(OUT / "technique_07_cagr.csv")
    vals = {r["metric"]: float(r["value"]) for r in t07}
    check("t07 revenue_2023", vals["revenue_2023_pkr"] == yearly["2023"])
    check("t07 revenue_2025", vals["revenue_2025_pkr"] == yearly["2025"])
    check("t07 years", vals["years"] == 2)
    check("t07 CAGR", close(vals["cagr_pct"], cagr))
    check("t07 avg monthly growth", close(vals["avg_monthly_growth_pct"],
                                           geo))
    check("t07 total", vals["total_revenue_2023_2025_pkr"] == grand)
    check("t07 months", vals["months"] == 36)

    # ---------- technique_08: best / worst ----------
    t08 = read_csv(OUT / "technique_08_best_worst_periods.csv")
    check("t08 row count 16", len(t08) == 16, f"got {len(t08)}")
    ranked_m = sorted(months, key=lambda m: -by_month[m]["revenue"])
    ranked_q = sorted(by_quarter, key=lambda q: -by_quarter[q])
    for lst, ranked, key in [
            ("best_months", ranked_m[:5], "month"),
            ("worst_months", ranked_m[-5:][::-1], "month"),
            ("best_quarters", ranked_q[:3], "quarter"),
            ("worst_quarters", ranked_q[-3:][::-1], "quarter")]:
        got = [(r["period"], int(r["revenue_pkr"])) for r in t08
               if r["list"] == lst]
        source = by_month if key == "month" else by_quarter
        expect = [(p, source[p]["revenue"] if key == "month"
                   else source[p]) for p in ranked]
        check(f"t08 {lst}", got == expect, f"{got} vs {expect}")
        ranks = [int(r["rank"]) for r in t08 if r["list"] == lst]
        check(f"t08 {lst} ranks", ranks == list(range(1, len(ranks) + 1)))

    # ---------- technique_09: forecast + backtest ----------
    t09 = read_csv(OUT / "technique_09_forecast_backtest.csv")
    check("t09 row count 6", len(t09) == 6, f"got {len(t09)}")
    bt = [r for r in t09 if r["kind"] == "backtest"]
    fc = [r for r in t09 if r["kind"] == "forecast"]
    check("t09 backtest months",
          [r["month"] for r in bt] == ["2025-10", "2025-11", "2025-12"])
    check("t09 forecast months",
          [r["month"] for r in fc] == ["2026-01", "2026-02", "2026-03"])
    last_train = by_month["2025-09"]["revenue"]
    dec_2025 = by_month["2025-12"]["revenue"]
    naive_errs, seas_errs = [], []
    for r in bt:
        m = r["month"]
        actual = by_month[m]["revenue"]
        check(f"t09 {m} actual", int(r["actual_revenue_pkr"]) == actual)
        check(f"t09 {m} naive = Sep 2025",
              int(r["naive_forecast_pkr"]) == last_train)
        prior = by_month[f"2024-{m[5:]}"]["revenue"]
        check(f"t09 {m} seasonal-naive = same month 2024",
              int(r["seasonal_naive_forecast_pkr"]) == prior)
        n_err = round(abs(actual - last_train) / actual * 100, 2)
        s_err = round(abs(actual - prior) / actual * 100, 2)
        check(f"t09 {m} naive APE",
              close(float(r["naive_abs_pct_error"]), n_err))
        check(f"t09 {m} seasonal-naive APE",
              close(float(r["seasonal_naive_abs_pct_error"]), s_err))
        naive_errs.append(n_err)
        seas_errs.append(s_err)
    check("summary MAPE naive",
          close(summary["mape_naive_pct"],
                sum(naive_errs) / 3))
    check("summary MAPE seasonal-naive",
          close(summary["mape_seasonal_naive_pct"],
                sum(seas_errs) / 3))
    check("seasonal-naive beats naive on MAPE",
          sum(seas_errs) / 3 < sum(naive_errs) / 3)
    for r, prior_m in zip(fc, ["2025-01", "2025-02", "2025-03"]):
        check(f"t09 {r['month']} naive = Dec 2025",
              int(r["naive_forecast_pkr"]) == dec_2025)
        check(f"t09 {r['month']} seasonal-naive = {prior_m}",
              int(r["seasonal_naive_forecast_pkr"])
              == by_month[prior_m]["revenue"])
        check(f"t09 {r['month']} actual blank",
              r["actual_revenue_pkr"] in ("", None))
    check("summary forecast Jan 2026 seasonal-naive",
          summary["forecast_jan_2026_seasonal_naive_pkr"]
          == by_month["2025-01"]["revenue"])

    # ---------- technique_10: weekday vs weekend ----------
    t10 = read_csv(OUT / "technique_10_weekday_weekend.csv")
    check("t10 row count 7", len(t10) == 7)
    check("t10 weekday order Mon–Sun",
          [r["day_of_week"] for r in t10] == DAY_NAMES)
    by_dow = defaultdict(lambda: {"days": 0, "units": 0, "revenue": 0})
    for r, d in zip(rows, dates):
        k = by_dow[DAY_NAMES[d.weekday()]]
        k["days"] += 1
        k["units"] += int(r["units"])
        k["revenue"] += int(r["revenue"])
    for r in t10:
        dow = r["day_of_week"]
        check(f"t10 {dow} days", int(r["days"]) == by_dow[dow]["days"])
        check(f"t10 {dow} units",
              int(r["total_units"]) == by_dow[dow]["units"])
        check(f"t10 {dow} revenue",
              int(r["total_revenue_pkr"]) == by_dow[dow]["revenue"])
        check(f"t10 {dow} avg daily revenue",
              close(float(r["avg_daily_revenue_pkr"]),
                    by_dow[dow]["revenue"] / by_dow[dow]["days"]))
    check("t10 revenue sums to grand",
          sum(int(r["total_revenue_pkr"]) for r in t10) == grand)
    wknd_days = [d for d in dates if d.weekday() >= 5]
    wkday_days = [d for d in dates if d.weekday() < 5]
    wknd_rev = sum(int(r["revenue"]) for r, d in zip(rows, dates)
                   if d.weekday() >= 5)
    wkday_rev = sum(int(r["revenue"]) for r, d in zip(rows, dates)
                    if d.weekday() < 5)
    wknd_avg = wknd_rev / len(wknd_days)
    wkday_avg = wkday_rev / len(wkday_days)
    gap = (wknd_avg - wkday_avg) / wkday_avg * 100
    check("summary weekend avg daily",
          close(summary["avg_daily_revenue_weekend_pkr"], wknd_avg))
    check("summary weekday avg daily",
          close(summary["avg_daily_revenue_weekday_pkr"], wkday_avg))
    check("summary weekend gap pct",
          close(summary["weekend_vs_weekday_gap_pct"], gap),
          f"{summary['weekend_vs_weekday_gap_pct']} vs {gap:.2f}")
    check("weekend beats weekday", wknd_avg > wkday_avg)
    check("summary best day is Saturday",
          summary["avg_daily_revenue_weekend_pkr"] > 0)

    # ---------- findings.md + README.md carry the real numbers ------
    findings = (OUT / "findings.md").read_text()
    readme = (ROOT / "README.md").read_text()
    for label, text in [("findings", findings), ("README", readme)]:
        check(f"{label} has grand total", f"{grand:,}" in text)
        check(f"{label} has peak month", peak_m in text)
        check(f"{label} has CAGR",
              f"{round(cagr, 2)}" in text)
        check(f"{label} has MAPE naive",
              f"{round(sum(naive_errs) / 3, 2)}" in text)
        check(f"{label} has MAPE seasonal-naive",
              f"{round(sum(seas_errs) / 3, 2)}" in text)
        check(f"{label} has weekend gap",
              f"{round(gap, 1)}" in text or f"{round(gap, 2)}" in text)
        check(f"{label} has SAMPLE banner", "SAMPLE" in text)
        check(f"{label} has 1,096 rows", "1,096" in text)

    # ---------- generator determinism ----------
    with tempfile.TemporaryDirectory() as td:
        regen = Path(td) / "sales_daily_SAMPLE.csv"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / "generate_data.py"),
             "--out", str(regen)],
            capture_output=True, text=True)
        check("generator re-runs cleanly", proc.returncode == 0,
              proc.stderr[-300:])
        if proc.returncode == 0:
            h1 = hashlib.sha256(RAW.read_bytes()).hexdigest()
            h2 = hashlib.sha256(regen.read_bytes()).hexdigest()
            check("generator deterministic (byte-identical)", h1 == h2)

    print(f"{PASSED} checks passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILURES:")
        for f in FAILED:
            print(" -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
