"""
Exploratory analysis of the enriched 311 data.
Run from civicpulse:  python analytics/trends/eda_311.py
Writes tables to data/interim/eda/ (local) and charts to docs/figures/.

IMPORTANT scope finding (see docs/data_quality_report.md section 2.8):
the layer is a rolling one-year window. Every closed request has a close date on or
after 2025-11-07 (= ReportStartingDate). Requests opened earlier appear only because
they were closed inside the window or are still open. So:
  * "Window cohort" = opened on or after 2025-11-07. These are fully represented.
  * Older-opened requests are a biased survivor set and are left out of volume and
    resolution analysis. They are still counted in the open backlog.
  * Multi-year trends and year-over-year comparisons are NOT possible from this layer.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

IN_PATH = Path("data/processed/311/311_enriched.parquet")
TABLE_DIR = Path("data/interim/eda")
FIG_DIR = Path("docs/figures")
TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_START = pd.Timestamp("2025-11-07", tz="America/Chicago")  # ReportStartingDate (local midnight)
MATURE_END = pd.Timestamp("2026-08-01", tz="America/Chicago")  # at least ~3.5 months to resolve

pd.set_option("display.width", 200)

df = pd.read_parquet(IN_PATH)
df["opened_ym"] = df["opened_local"].dt.tz_localize(None).dt.to_period("M")
cohort = df[df["opened_utc"] >= WINDOW_START].copy()
mature = cohort[(cohort["opened_utc"] < MATURE_END) & cohort["is_valid_resolution"]]
open_all = df[df["case_status"] == "OPEN"]
closed_cohort = cohort[cohort["case_status"] == "CLOSED"]


def save(table, name):
    table.to_csv(TABLE_DIR / f"{name}.csv")


print("All rows:", len(df), "| window cohort:", len(cohort),
      "| opened before window:", len(df) - len(cohort))
print("Mature cohort (opened before 2026-08-01, valid resolution):", len(mature))

# 1. Monthly volume: complete local months only (Dec 2025 - Oct 2026)
print("\n--- 1. MONTHLY VOLUME (cohort) ---")
monthly = cohort.groupby("opened_ym").size()
complete = monthly[(monthly.index >= "2025-12") & (monthly.index <= "2026-10")]
print(monthly.to_string())
print("complete months:", len(complete), "mean:", round(complete.mean()),
      "min:", complete.min(), complete.idxmin(), "max:", complete.max(), complete.idxmax())
save(monthly.rename("requests"), "monthly_volume_cohort")

# 2. Mix
print("\n--- 2. CATEGORY SHARE (cohort %) ---")
cat = cohort["category"].value_counts()
print((cat / len(cohort) * 100).round(1).to_string())
print("\n--- DEPARTMENT SHARE (cohort %) ---")
print((cohort["department"].value_counts() / len(cohort) * 100).round(1).to_string())
print("\n--- TOP 10 TYPES (cohort) ---")
print(cohort["type_name"].value_counts().head(10).to_string())

# 3. Category by month (top 5)
top5 = cat.head(5).index
cm = pd.crosstab(cohort["opened_ym"], cohort["category"])[top5]
print("\n--- 3. TOP-5 CATEGORIES BY MONTH ---")
print(cm.to_string())
save(cm, "category_by_month")

# 4. Backlog (all open, snapshot)
print("\n--- 4. OPEN BACKLOG (snapshot 2026-11-13) ---")
days = open_all["open_age_hours"] / 24
labels = ["0-7", "8-30", "31-90", "91-365", ">365"]
bk = pd.cut(days, [-1, 7, 30, 90, 365, 10_000], labels=labels).value_counts().reindex(labels)
print(bk.to_string())
print("total open:", len(open_all), "median age days:", round(days.median(), 1))
print("open requests opened before window:", int((open_all["opened_utc"] < WINDOW_START).sum()))
tab = pd.DataFrame({
    "open": open_all["department"].value_counts(),
    "all_rows": df["department"].value_counts(),
})
tab["open_pct"] = (tab["open"] / tab["all_rows"] * 100).round(1)
print("\nOpen by department:")
print(tab.sort_values("open", ascending=False).to_string())
save(bk, "backlog_age_buckets")

# 5. Resolution (mature cohort only)
print("\n--- 5. RESOLUTION (mature cohort, valid closed) ---")
rh = mature["resolution_hours"]
print("n:", len(rh), "median h:", round(rh.median(), 1), "mean h:", round(rh.mean(), 1))
print("p25/p75/p90/p95/p99 h:", [round(x, 1) for x in rh.quantile([.25, .75, .9, .95, .99])])
print("closed within 24h / 7d / 30d %:", [round(float((rh <= h).mean() * 100), 1) for h in (24, 168, 720)])
bycat = mature.groupby("category")["resolution_hours"].agg(["count", "median"]).sort_values("median")
bydep = mature.groupby("department")["resolution_hours"].agg(["count", "median"]).sort_values("median")
print("\nMedian hours by category:\n", bycat.round(1).to_string())
print("\nMedian hours by department:\n", bydep.round(1).to_string())
save(bycat, "resolution_by_category")
save(bydep, "resolution_by_department")

# 6. Late rate (source flag), closed cohort
print("\n--- 6. LATE RATE (source flag, closed cohort) ---")
print("overall %:", round(closed_cohort["is_late_source"].mean() * 100, 1))
print((closed_cohort.groupby("department")["is_late_source"].mean() * 100).round(1).sort_values(ascending=False).to_string())

# 7. Time patterns (cohort)
print("\n--- 7. WEEKDAY / HOUR (cohort, local time) ---")
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
wd = cohort["opened_weekday"].value_counts().reindex(order)
print(wd.to_string())
hr = cohort["opened_hour"].value_counts().sort_index()
print("peak hour:", hr.idxmax(), "| share opened 5-9am:", round(hr.loc[5:9].sum() / hr.sum() * 100, 1), "%")
print(hr.to_string())

# 8. Council district
print("\n--- 8. COUNCIL DISTRICT (cohort) ---")
cd = cohort.groupby("council_district").agg(
    requests=("case_id", "size"),
    open_pct=("case_status", lambda s: round((s == "OPEN").mean() * 100, 1)),
)
cd["median_res_h"] = mature.groupby("council_district")["resolution_hours"].median().round(1)
print(cd.to_string())
save(cd, "council_district")
d0 = cohort[cohort["council_district"] == 0]
print("\nDistrict 0 rows:", len(d0), f"({len(d0) / len(cohort) * 100:.1f}%)")
print("District 0 by department %:", (d0["department"].value_counts(normalize=True) * 100).round(1).head(4).to_dict())

# 9. Channels
print("\n--- 9. SOURCE CHANNEL (cohort %) ---")
print((cohort["source_channel"].value_counts(normalize=True) * 100).round(1).to_string())

# 10. Right-censoring check
print("\n--- 10. CENSORING: open share by opened month (cohort) ---")
print((cohort.groupby("opened_ym")["case_status"].apply(lambda s: round((s == "OPEN").mean() * 100, 1))).to_string())

# Charts
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
BLUE = "#1b5fc1"

fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(complete.index.astype(str), complete.values, color=BLUE)
ax.set_title("311 requests opened per month (complete months, Dec 2025 to Oct 2026)")
ax.set_ylabel("Requests"); ax.grid(axis="y", alpha=.3); plt.xticks(rotation=45, ha="right")
fig.tight_layout(); fig.savefig(FIG_DIR / "monthly_volume.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
cat.sort_values().plot.barh(ax=ax, color=BLUE)
ax.set_title("Requests by category (opened Nov 2025 to Nov 2026)"); ax.set_xlabel("Requests")
fig.tight_layout(); fig.savefig(FIG_DIR / "category_volume.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
bk.plot.bar(ax=ax, color=BLUE, rot=0)
ax.set_title("Open backlog by age in days (snapshot 2026-11-13)"); ax.set_ylabel("Open requests")
fig.tight_layout(); fig.savefig(FIG_DIR / "backlog_age.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4.5))
(bycat["median"] / 24).plot.barh(ax=ax, color=BLUE)
ax.set_title("Median resolution time by category, days\n(requests opened Nov 2025 to Jul 2026)"); ax.set_xlabel("Days")
fig.tight_layout(); fig.savefig(FIG_DIR / "resolution_by_category.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
wd.plot.bar(ax=ax, color=BLUE, rot=30)
ax.set_title("Requests by weekday opened (local time)"); ax.set_ylabel("Requests")
fig.tight_layout(); fig.savefig(FIG_DIR / "weekday.png", dpi=150); plt.close(fig)

print("\nCharts written to", FIG_DIR)
