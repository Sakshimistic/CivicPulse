# SQL Business Queries

Files: `database/queries/*.sql`. Runner: `python database/run_queries.py` (prints a preview and writes CSVs to `data/interim/sql_results/`).
All queries read the `civicpulse` star schema. Unless noted, they use the **window cohort** (`in_report_window`, opened on or after 2025-11-07 local).

| File | KPI | Notes |
|---|---|---|
| `01_monthly_volume` | Requests per month, month-over-month change | Complete months only (Dec 2025 to Oct 2026) |
| `02_category_volume` | Volume and share by category | |
| `03_department_scorecard` | Volume, open share, median resolution by department | |
| `04_backlog_age_buckets` | Open backlog by age bucket | All open cases, age at snapshot |
| `05_backlog_by_department` | Open count, median and oldest age by department | All open cases |
| `06_resolution_by_category` | Median, p90, mean resolution hours | Mature cohort (opened before 2026-08-01), categories with 100+ cases |
| `07_resolution_data_coverage` | Share of closed cases usable for resolution metrics | Data-quality indicator |
| `08_late_rate_by_department` | Share of closed cases marked late by the city | Source flag, meaning unverified |
| `09_district_volume` | Volume and open count by council district | District 0 shown as Unassigned |
| `10_weekday_hour_pattern` | Requests by weekday and local hour | |
| `11_channel_mix` | Intake channel share and median resolution | |
| `12_top_request_types` | Top 15 request types with open share and median resolution | |

## Verified against pandas

Monthly counts (Dec 2025, Jun 2026, Oct 2026), category totals, District 0 count, late rate (7.3% of 472,528 closed), open count (25,411) and median open age (83.1 days) match the pandas results exactly.

## What the results show (this snapshot)

- Volume is about 41k to 51k a month, peaking in June 2026 (51,401).
- Solid Waste (33.9%), Property Maintenance (28.5%) and Animals (15.5%) are 78% of requests.
- Median resolution ranges from about 6 hours (Graffiti, Animals, Traffic Signals) to 1,285 hours (Homeless). Property Maintenance is 136 hours.
- Development Services holds 14,656 of the 25,411 open cases. 46% of the open backlog is 91 to 365 days old.
- Resolution data covers 99.83% of closed cases.
- WOM (staff-entered) requests take a median 217.6 hours against 28.9 for web, partly because of the categories they cover.

## Caveats to keep with any claim

- Differences between departments and categories reflect different work types, not performance. These are descriptive numbers.
- Late rate uses the city's `LateYesNo` flag as given. 12,283 cases closed after their SLA date are marked NO, so its meaning is unconfirmed.
- 16.6% of requests have District 0 (Unassigned). District counts are not per-capita rates.
- Backlog counts depend on the snapshot time (2026-11-13) and include cases opened before the window.
