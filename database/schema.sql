-- CivicPulse warehouse: star schema for San Antonio 311 service requests.
-- Grain of the fact table: one row per service request (case_id).
-- Run by database/load_postgres.py (drops and recreates the schema). See docs/data_model.md.

DROP SCHEMA IF EXISTS civicpulse CASCADE;
CREATE SCHEMA civicpulse;
SET search_path TO civicpulse;

-- ---------------------------------------------------------------------------
-- Load log: one row per load. Holds the snapshot time used for open-request age.
-- ---------------------------------------------------------------------------
CREATE TABLE etl_load_log (
    load_id          serial PRIMARY KEY,
    loaded_at        timestamptz NOT NULL DEFAULT now(),
    source_file      text        NOT NULL,
    snapshot_ts      timestamptz NOT NULL,   -- extraction time (UTC) from the manifest
    fact_rows        integer     NOT NULL,
    window_start_ts  timestamptz NOT NULL    -- start of the layer's reporting window
);

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key      integer PRIMARY KEY,        -- yyyymmdd
    full_date     date    NOT NULL UNIQUE,
    year          smallint NOT NULL,
    quarter       smallint NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month         smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name    text    NOT NULL,
    year_month    text    NOT NULL,           -- 'YYYY-MM'
    day_of_month  smallint NOT NULL,
    iso_weekday   smallint NOT NULL CHECK (iso_weekday BETWEEN 1 AND 7),  -- 1 = Monday
    weekday_name  text    NOT NULL,
    is_weekend    boolean NOT NULL
);

CREATE TABLE dim_department (
    department_key  serial PRIMARY KEY,
    department_name text NOT NULL UNIQUE
);

CREATE TABLE dim_issue_type (
    issue_type_key  serial PRIMARY KEY,
    category        text NOT NULL,            -- cleaned category ('Unknown' when missing in source)
    reason_name     text NOT NULL,
    type_name       text NOT NULL,
    UNIQUE (category, reason_name, type_name)
);

-- Council district 0 is not a real district; it is shown as 'Unassigned'.
CREATE TABLE dim_council_district (
    district_key    smallint PRIMARY KEY,     -- equals the source CouncilDistrict value
    district_label  text NOT NULL,
    is_assigned     boolean NOT NULL
);

CREATE TABLE dim_source_channel (
    channel_key     serial PRIMARY KEY,
    channel_code    text NOT NULL UNIQUE,     -- normalized: voice_in, web, wom, ...
    channel_label   text NOT NULL
);

-- ---------------------------------------------------------------------------
-- Fact table
-- ---------------------------------------------------------------------------
CREATE TABLE fact_service_request (
    case_id              bigint PRIMARY KEY,                  -- business key (unique in source)
    objectid             bigint NOT NULL UNIQUE,              -- ArcGIS row id

    opened_date_key      integer  NOT NULL REFERENCES dim_date (date_key),
    closed_date_key      integer  REFERENCES dim_date (date_key),
    department_key       integer  NOT NULL REFERENCES dim_department (department_key),
    issue_type_key       integer  NOT NULL REFERENCES dim_issue_type (issue_type_key),
    district_key         smallint NOT NULL REFERENCES dim_council_district (district_key),
    channel_key          integer  NOT NULL REFERENCES dim_source_channel (channel_key),

    opened_ts            timestamptz NOT NULL,                -- true UTC (derived from local wall-clock time)
    closed_ts            timestamptz,
    sla_ts               timestamptz,
    opened_hour          smallint NOT NULL CHECK (opened_hour BETWEEN 0 AND 23),  -- local hour

    case_status          text NOT NULL CHECK (case_status IN ('OPEN', 'CLOSED')),
    is_late_source       boolean NOT NULL,                    -- the city's own LateYesNo flag
    resolution_hours     numeric(14, 4),                      -- only when is_valid_resolution

    is_valid_resolution  boolean NOT NULL,
    invalid_close_date   boolean NOT NULL,
    negative_duration    boolean NOT NULL,
    invalid_sla_date     boolean NOT NULL,
    category_was_missing boolean NOT NULL,
    has_description      boolean NOT NULL,
    in_report_window     boolean NOT NULL,                    -- fully represented cohort

    latitude             double precision NOT NULL,
    longitude            double precision NOT NULL,
    x_coord              integer NOT NULL,                    -- EPSG:2278, US survey feet
    y_coord              integer NOT NULL,

    CHECK ((case_status = 'OPEN') = (closed_ts IS NULL AND closed_date_key IS NULL)
           OR invalid_close_date),
    CHECK (resolution_hours IS NULL OR resolution_hours >= 0),
    CHECK (resolution_hours IS NULL OR is_valid_resolution)
);

-- Indexes chosen for the planned queries (trend, backlog, department, district, map).
CREATE INDEX ix_fact_opened_date   ON fact_service_request (opened_date_key);
CREATE INDEX ix_fact_department    ON fact_service_request (department_key);
CREATE INDEX ix_fact_issue_type    ON fact_service_request (issue_type_key);
CREATE INDEX ix_fact_district      ON fact_service_request (district_key);
CREATE INDEX ix_fact_open          ON fact_service_request (opened_ts) WHERE case_status = 'OPEN';
CREATE INDEX ix_fact_window        ON fact_service_request (opened_date_key) WHERE in_report_window;

-- ---------------------------------------------------------------------------
-- Views (the surface the SQL queries, API and AI assistant will use)
-- ---------------------------------------------------------------------------
-- Denormalised view for convenience.
CREATE VIEW v_service_request AS
SELECT f.*,
       d.full_date AS opened_date, d.year_month AS opened_year_month,
       d.weekday_name AS opened_weekday, d.is_weekend,
       dep.department_name,
       it.category, it.reason_name, it.type_name,
       cd.district_label,
       sc.channel_code
FROM fact_service_request f
JOIN dim_date d              ON d.date_key = f.opened_date_key
JOIN dim_department dep      ON dep.department_key = f.department_key
JOIN dim_issue_type it       ON it.issue_type_key = f.issue_type_key
JOIN dim_council_district cd ON cd.district_key = f.district_key
JOIN dim_source_channel sc   ON sc.channel_key = f.channel_key;

-- Open backlog with age as of the latest load's snapshot time.
CREATE VIEW v_open_backlog AS
SELECT f.case_id, f.opened_ts, dep.department_name, it.category, it.type_name,
       cd.district_label, f.in_report_window,
       EXTRACT(EPOCH FROM (l.snapshot_ts - f.opened_ts)) / 3600.0 AS open_age_hours
FROM fact_service_request f
JOIN dim_department dep      ON dep.department_key = f.department_key
JOIN dim_issue_type it       ON it.issue_type_key = f.issue_type_key
JOIN dim_council_district cd ON cd.district_key = f.district_key
CROSS JOIN (SELECT snapshot_ts FROM etl_load_log ORDER BY load_id DESC LIMIT 1) l
WHERE f.case_status = 'OPEN';

-- Requests that count toward resolution metrics.
CREATE VIEW v_resolution AS
SELECT case_id, opened_date_key, department_key, issue_type_key, district_key, resolution_hours
FROM fact_service_request
WHERE is_valid_resolution AND in_report_window;
