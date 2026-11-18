# Data Dictionary

Describes the curated file `data/processed/311/311_enriched.parquet` (39 columns, 510,535 rows, one row per 311 request).
Source: City of San Antonio 311 All Service Calls (ArcGIS). Built by `clean_311.py` then `enrich_311.py`.
Timestamps are timezone-aware. Raw values are Unix milliseconds in UTC.

## Identifiers
| Column | Type | Meaning |
|---|---|---|
| `objectid` | int | ArcGIS row id. Unique. |
| `case_id` | int | Service request id. Unique. Business key. |

## Time (UTC kept, local derived)
| Column | Type | Meaning |
|---|---|---|
| `opened_utc` | datetime (UTC) | When the request was opened. |
| `closed_utc` | datetime (UTC) | When closed. Null for open cases and for 780 invalid 1900 placeholders. |
| `sla_utc` | datetime (UTC) | Source SLA/target date. Meaning unverified. Null where it was a 1899/1900 placeholder. |
| `opened_local` | datetime (America/Chicago) | Opened time in San Antonio local time. |
| `closed_local` | datetime (America/Chicago) | Closed time in local time. |
| `opened_date` | date | Local opened date. |
| `opened_year`, `opened_month`, `opened_hour` | int | Local year, month (1-12), hour (0-23). |
| `opened_weekday` | string | Local weekday name. |

## Status and performance
| Column | Type | Meaning |
|---|---|---|
| `case_status` | string | `OPEN` or `CLOSED`, as in the source. |
| `late_yes_no` | string | Source late indicator (`YES`/`NO`). Definition unverified. |
| `is_late_source` | bool | `late_yes_no = 'YES'`. |
| `is_valid_resolution` | bool | Closed, has a valid close date, and not a negative duration. Basis for resolution metrics. |
| `resolution_hours` | float | Closed minus opened, in hours. Only when `is_valid_resolution`; otherwise null. |
| `open_age_hours` | float | Snapshot time minus opened time, in hours. Open cases only; otherwise null. |

## Data-quality flags
| Column | Type | Meaning |
|---|---|---|
| `invalid_close_date` | bool | Source close date was a 1900 placeholder (780 rows). |
| `negative_duration` | bool | Close time earlier than open time, not the placeholder (2 rows). |
| `invalid_sla_date` | bool | Source SLA date was a pre-2000 placeholder (537 rows). |
| `category_was_missing` | bool | Source category was null (220 rows). |
| `has_description` | bool | Source description was present. |
| `coord_in_expected_area` | bool | Converted coordinates fall inside a loose San Antonio box. True for all rows. |

## Classification
| Column | Type | Meaning |
|---|---|---|
| `category_source` | string | Original category, null preserved. |
| `category` | string | Category with nulls replaced by `Unknown`. Use this for analysis. |
| `department` | string | Responsible department. |
| `reason_name` | string | Reason grouping. Blank for the 220 missing-category rows. |
| `type_name` | string | Specific request type. |
| `source_id_original` | string | Original intake channel value. |
| `source_channel` | string | Normalized channel: `voice_in`, `web`, `wom`, `voice_out`, `face_to_face`, `email_in`, `email_out`. |
| `object_description` | string | Address/description text. Sensitive. Mostly missing for older records. |

## Geography
| Column | Type | Meaning |
|---|---|---|
| `council_district` | int | Council district as in the source. Not yet validated against boundaries. |
| `x_coord`, `y_coord` | int | Projected coordinates, EPSG:2278 (NAD83 / Texas South Central, US survey feet). |
| `geometry_x`, `geometry_y` | float | Same location from the feature geometry. Matches `x_coord`/`y_coord` after rounding. |
| `longitude`, `latitude` | float | WGS84 degrees (EPSG:4326), converted with pyproj. |

## Dropped from the source
`ReportStartingDate` and `ReportEndingDate` are constant on every row (layer report-window metadata), so they are not carried over.
