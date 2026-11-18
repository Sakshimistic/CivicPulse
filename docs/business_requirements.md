# Business Requirements and KPI Definitions

**Project:** CivicPulse (portfolio case study using public San Antonio 311 data)
**Status:** KPI definitions agreed for the first build. Items marked *unverified* depend on source meanings not yet confirmed.

## 1. Problem statement

A hypothetical city operations team receives hundreds of thousands of 311 requests and needs a reliable, documented view of demand, backlog, resolution speed and geographic patterns. The platform must make every number traceable to a clear definition.

## 2. Audience

City operations leadership, 311 program managers, department managers, data and business analysts.

## 3. Business questions

1. How is request volume changing over time?
2. Which categories, request types and departments carry the most workload?
3. How large is the open backlog and how old is it?
4. How do volume and resolution performance vary by council district?
5. Which issue types or areas show recurring demand or unusual spikes?
6. Are there descriptive relationships between weather and relevant categories?
7. How does volume compare across areas after accounting for population?
8. Can an AI assistant answer these using verified metrics?

## 4. Global rules for every KPI

- **Grain:** one row per `case_id` (unique in the source).
- **Period:** a request belongs to the period of its opened date, in San Antonio local time (`America/Chicago`) unless stated otherwise.
- **Snapshot:** backlog and open-age metrics are as of the extraction time, stored in the manifest (current snapshot: 2026-11-13 21:59:50 UTC). Always show the snapshot date next to them.
- **Category:** use the cleaned `category`, which includes `Unknown`. Never drop `Unknown`.
- **Window cohort:** the layer is a rolling one-year window (see data quality report 2.8). Volume, mix and resolution KPIs use requests with `in_report_window = true` (opened on or after 2025-11-07). Requests opened earlier are a biased survivor set. They count only toward the open backlog.
- **No multi-year trends:** year-over-year change cannot be calculated from this layer. Seasonality covers one year.
- **Complete periods:** trend and change metrics use complete months only (currently Dec 2025 to Oct 2026). Data ends 2026-11-06.
- **Maturity:** resolution KPIs use requests opened at least 3 months before the snapshot, because recent requests that are still open would bias resolution times short.
- **Districts:** `council_district = 0` is shown as "Unassigned" and is not treated as a district.
- **Excluded records:** flagged records stay in the data. They are excluded only from the metrics named below, and the excluded count is shown.

## 5. KPI definitions

| KPI | Formula | Uses | Exclusions / caveats |
|---|---|---|---|
| Total requests | Count of distinct `case_id` opened in the period | `case_id`, `opened_local` | None. |
| Open backlog | Count where `case_status = 'OPEN'` | `case_status` | Snapshot-dependent. |
| Closed requests | Count where `case_status = 'CLOSED'` | `case_status` | Includes 780 records with an invalid close date (status as in source). |
| Median resolution hours | Median of `resolution_hours` | `resolution_hours` | Only rows with `is_valid_resolution = true`. 782 closed records excluded in the current snapshot. Median is the headline metric because durations are heavily skewed. |
| Mean resolution hours | Mean of `resolution_hours` | same | Secondary metric, sensitive to long outliers (max about 5 years). |
| Resolution-data coverage | Valid-resolution records / closed requests | flags | Data-quality indicator, not performance. |
| Open request age | Snapshot time minus `opened_utc`, in hours or days | `open_age_hours` | Open cases only. |
| Backlog age buckets | Open cases grouped 0-7, 8-30, 31-90, 91-365, over 365 days | `open_age_hours` | Bucket edges are a presentation choice. |
| Late rate (source flag) | Closed requests with `is_late_source` / closed requests | `late_yes_no` | *Unverified:* meaning of `LateYesNo` is not confirmed. Report as "marked late by the city", never recompute from `sla_utc`. |
| Volume by category / department / type | Count of `case_id` grouped by the field | `category`, `department`, `type_name` | Department is the owning department as recorded. Ownership semantics unconfirmed. |
| Volume by council district | Count of `case_id` grouped by `council_district` | `council_district` | Verify district values against official boundaries before district-level claims. |
| Month-over-month change | (Month volume - prior month volume) / prior month volume | monthly counts | Complete months only. |
| Year-over-year change | Same period this year vs last year | monthly counts | **Not available** from this layer (one-year window). Needs another source or repeated snapshots. |
| Day / hour pattern | Count by `opened_weekday`, `opened_hour` | local-time fields | Local time. |
| Requests per 1,000 residents | Requests / population x 1,000 | Census ACS | Only when geography and year align. Planned, needs Census data. |
| Repeat issue rate | Defined repeats in a spatial and time window | `latitude`, `longitude`, `category` | Planned. Spatial and time rules to be set in the analytics phase. |
| Geographic hotspot | Statistically or operationally defined concentration | coordinates | Planned. Do not equate raw counts with need. |

## 6. Rules the analysis must not break

- Do not invent service-level targets. Overdue means only what the source SLA fields support, and that is currently unverified.
- Weather and demographic comparisons are descriptive. No causal claims.
- No exact residential addresses in public dashboards. `object_description` is for internal use only.
- Do not claim citywide coverage until the layer's scope is verified.
- Do not state an update cadence until it is observed over several extractions.
- Do not claim the City of San Antonio used or benefited from this project.

## 7. Known data limitations that affect KPIs

See `docs/data_quality_report.md`. In short: 780 placeholder close dates and 2 negative durations affect resolution metrics, 220 missing categories appear as `Unknown`, descriptions are mostly missing for older records, and SLA semantics are unconfirmed.

## 8. Success criteria (portfolio targets, not claims of real outcomes)

- Python, SQL and Power BI report the same value for each KPI above.
- Every KPI has a definition, a formula and its caveats in this document.
- Each excluded-record count is visible wherever its metric is shown.
