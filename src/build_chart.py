"""Build outputs/monthly_revenue_trend.png — Mini #21.

Monthly revenue (bars) with the 12-month moving average (line),
from outputs/technique_01_monthly_resample.csv and
outputs/technique_02_rolling_averages.csv. Re-run any time:
python3 src/build_chart.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"


def main():
    monthly = pd.read_csv(OUT / "technique_01_monthly_resample.csv")
    rolling = pd.read_csv(OUT / "technique_02_rolling_averages.csv")
    assert list(monthly["month"]) == list(rolling["month"])

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(monthly["month"], monthly["revenue_pkr"] / 1e6,
           color="#7fb3d5", label="Monthly revenue (PKR millions)")
    ax.plot(rolling["month"], rolling["ma_12m_pkr"] / 1e6,
            color="#1a5276", linewidth=2.5,
            label="12-month moving average")
    ax.set_title("Noor Electronics — monthly revenue & 12-month trend\n"
                 "SAMPLE data, Jan 2023 – Dec 2025", fontsize=13)
    ax.set_xlabel("Month")
    ax.set_ylabel("PKR millions")
    ax.tick_params(axis="x", labelrotation=45)
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = OUT / "monthly_revenue_trend.png"
    fig.savefig(path, dpi=150)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
