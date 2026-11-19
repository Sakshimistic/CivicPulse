# Data Model: PostgreSQL Star Schema

Files: `database/schema.sql` (DDL), `database/load_postgres.py` (loader).
Schema name: `civicpulse`. Source: `data/processed/311/311_enriched.parquet`.

## Grain

`fact_service_request` has **one row per 311 service request** (`case_id`). 510,535 rows in the current snapshot.

## Diagram

```text
                         dim_date (2,245 rows)
                        /  (opened_date_key, closed_date_key)
dim_department ---+   /
 (9)               |  /
dim_issue_type ----+--- fact_service_request ---- dim_council_district (11, 0 = Unassigned)
 (242)             |         (510,535)
dim_source_channel-+
 (7)

etl_load_log: one row per load (snapshot time, row count, window start)
```

## Tables

| Table | Key | Rows | Purpose |
|---|---|---|---|
| `fact_service_request` | `case_id` | 510,535 | One row per request: timestamps, status, resolution hours, flags, coordinates |
| `dim_date` | `date_key` (yyyymmdd) | 2,245 | Calendar attributes: year, quarter, month, weekday, weekend flag |
| `dim_department` | `department_key` | 9 | Responsible department |
| `dim_issue_type` | `issue_type_key` | 242 | Category, reason and request type |
| `dim_council_district` | `district_key` (the source district number) | 11 | District label; 0 is shown as "Unassigned" |
| `dim_source_channel` | `channel_key` | 7 | Normalized intake channel |
| `etl_load_log` | `load_id` | 1 | Snapshot time and row count per load |

Views: `v_service_request` (denormalised), `v_open_backlog` (open cases with age at the latest snapshot), `v_resolution` (valid resolution records in the window cohort).

## Design decisions

1. **No `dim_location`.** The blueprint listed one, but every request has a unique point, so a location dimension would have as many rows as the fact table. Council district is its own small dimension, and latitude, longitude and the projected coordinates stay on the fact row.
2. **Status stays on the fact table.** `case_status` has two values (`OPEN`, `CLOSED`), so a dimension adds nothing. It is guarded by a check constraint.
3. **Department is separate from issue type.** One request type appears under two departments in the source, so department cannot be an attribute of the type.
4. **Date keys use local dates.** A request opened at 23:30 local stays on its own day. Timestamps are stored in true UTC (`timestamptz`) and the local hour is kept in `opened_hour`.
5. **Open-request age is not stored.** It depends on the snapshot time, so `v_open_backlog` computes it from `etl_load_log`.
6. **`object_description` is not loaded.** It contains address text and is mostly unneeded for the planned analysis. Sensitive text stays out of the warehouse.
7. **Flags are kept as columns, not rows removed.** `is_valid_resolution`, `invalid_close_date`, `negative_duration`, `invalid_sla_date`, `category_was_missing`, `has_description` and `in_report_window` let every metric state what it excludes.
8. **Surrogate keys** (serial integers) for the department, issue type and channel dimensions. The date key and district key are natural, meaningful values.
9. **Lateness is the city's own flag** (`is_late_source`), not recomputed.

## Integrity rules enforced by the database

- `case_id` and `objectid` unique.
- Every dimension key is a foreign key. `closed_date_key` may be null.
- `case_status` is `OPEN` or `CLOSED`.
- A request is open only if it has no close time. The exception is a closed request whose close date was an invalid placeholder (`invalid_close_date`).
- `resolution_hours` is null or non-negative, and only set when `is_valid_resolution`.
- `opened_hour` is between 0 and 23.

## Loading and reconciliation

`python database/load_postgres.py` creates the database if needed, drops and recreates the `civicpulse` schema, loads the dimensions then the fact table in one transaction, and checks:

- loaded row count equals the Parquet row count
- open-request count matches
- the SQL median resolution hours for the window cohort equals the pandas value

Settings come from `.env` (copy `.env.example`). The script uses the `psql` client that ships with PostgreSQL.

Verified on a throwaway PostgreSQL 18 instance: 510,535 rows loaded, 25,411 open, median resolution 42.003 hours in both SQL and pandas, zero orphan keys, and a bad row correctly rejected by the check constraint.

## Known limits

- The window cohort (`in_report_window`) must be applied in any volume or resolution query. The views `v_resolution` does this. `v_service_request` does not.
- Only one snapshot is loaded, and each load replaces the previous one. Keeping history across loads is a later decision.
- `district_key` 0 is unassigned until district boundaries are added.
