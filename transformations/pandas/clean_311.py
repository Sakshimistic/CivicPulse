"""
Clean the raw San Antonio 311 extraction into a curated Parquet file.

Run from the civicpulse folder:
    python transformations/pandas/clean_311.py
    python transformations/pandas/clean_311.py data/raw/311/extraction_20261113_215950

Rules are documented in docs/data_quality_report.md (section 4).
Raw files are only read, never modified. No rows are deleted.
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAW_ROOT = Path("data/raw/311")
OUT_DIR = Path("data/processed/311")
LOCAL_TZ = "America/Chicago"

DATE_COLUMNS = ["OpenedDateTime", "ClosedDateTime", "SLADate"]


# --------------------------------------------------
# 1. Locate and load the raw extraction
# --------------------------------------------------
def find_extraction_dir():
    """Use the path given on the command line, else the newest extraction folder."""
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    folders = sorted(RAW_ROOT.glob("extraction_*"))
    if not folders:
        sys.exit("No extraction folder found under " + str(RAW_ROOT))
    return folders[-1]


def load_raw(extraction_dir):
    records = []
    for batch_file in sorted(extraction_dir.glob("batch_*.json")):
        with open(batch_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for feature in data["features"]:
            record = feature["attributes"].copy()
            geometry = feature.get("geometry") or {}
            record["geometry_x"] = geometry.get("x")
            record["geometry_y"] = geometry.get("y")
            records.append(record)
    return pd.DataFrame(records)


# --------------------------------------------------
# 2. Cleaning steps
# --------------------------------------------------
def normalize_source(series):
    """voice_in / 'Voice in' -> voice_in, etc."""
    return (
        series.str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
    )


# The source stores San Antonio wall-clock time labelled as UTC. Evidence: requests
# ramp up sharply at 07:00-08:00 and fall off overnight when read as local time;
# read as true UTC they would peak at 3-10am Central. The layer metadata has no
# time-zone information, so this is an inference (docs/data_quality_report.md 2.9).
RAW_TIMES_ARE_LOCAL = True

# Start of the layer's reporting window (ReportStartingDate = 2025-11-07 00:00 local).
WINDOW_START = pd.Timestamp("2025-11-07", tz="UTC") + pd.Timedelta(hours=6)  # CST, UTC-6


def to_true_utc(series):
    """Raw values arrive labelled UTC. If they are really local wall-clock time,
    relabel them as America/Chicago and convert to true UTC.
    Ambiguous fall-back hours use standard time; missing spring-forward hours shift forward."""
    if not RAW_TIMES_ARE_LOCAL:
        return series
    local = series.dt.tz_localize(None).dt.tz_localize(
        LOCAL_TZ, ambiguous=False, nonexistent="shift_forward"
    )
    return local.dt.tz_convert("UTC")


def clean(df, snapshot_utc):
    out = pd.DataFrame()

    # Identifiers (unchanged)
    out["objectid"] = df["OBJECTID"]
    out["case_id"] = df["CaseID"]

    # Timestamps: raw is Unix milliseconds -> timezone-aware UTC
    raw_opened = pd.to_datetime(df["OpenedDateTime"], unit="ms", utc=True, errors="coerce")
    raw_closed = pd.to_datetime(df["ClosedDateTime"], unit="ms", utc=True, errors="coerce")
    raw_sla = pd.to_datetime(df["SLADate"], unit="ms", utc=True, errors="coerce")

    # Rule 1: 1900 placeholder close date -> NULL + flag
    out["invalid_close_date"] = raw_closed.dt.year < 2000
    closed = raw_closed.mask(out["invalid_close_date"])

    # Rule 5: SLADate placeholders (year < 2000) -> NULL
    out["invalid_sla_date"] = raw_sla.dt.year < 2000
    sla = raw_sla.mask(out["invalid_sla_date"])

    # Rule 8: raw values are local wall-clock time; convert to true UTC
    raw_opened = to_true_utc(raw_opened)
    closed = to_true_utc(closed)
    sla = to_true_utc(sla)

    # Rule 2: genuine negative duration (close before open, not the placeholder)
    out["negative_duration"] = (closed < raw_opened).fillna(False)

    # Rule 10: rolling-window cohort. The layer's ReportStartingDate (2025-11-07, local
    # midnight) marks where full coverage begins; earlier requests are survivors only.
    out["in_report_window"] = raw_opened >= WINDOW_START

    out["opened_utc"] = raw_opened
    out["closed_utc"] = closed
    out["sla_utc"] = sla

    # Rule 8: derive San Antonio local time; UTC columns are kept as-is
    out["opened_local"] = raw_opened.dt.tz_convert(LOCAL_TZ)
    out["closed_local"] = closed.dt.tz_convert(LOCAL_TZ)
    out["opened_date"] = out["opened_local"].dt.date
    out["opened_year"] = out["opened_local"].dt.year
    out["opened_month"] = out["opened_local"].dt.month
    out["opened_weekday"] = out["opened_local"].dt.day_name()
    out["opened_hour"] = out["opened_local"].dt.hour

    # Status and source-provided lateness (taken as given, not recomputed)
    out["case_status"] = df["CaseStatus"]
    out["late_yes_no"] = df["LateYesNo"]
    out["is_late_source"] = df["LateYesNo"].eq("YES")

    # Rule 3: resolution metrics only for valid closed records
    out["is_valid_resolution"] = (
        out["case_status"].eq("CLOSED")
        & closed.notna()
        & ~out["negative_duration"]
    )
    duration_hours = (closed - raw_opened).dt.total_seconds() / 3600
    out["resolution_hours"] = duration_hours.where(out["is_valid_resolution"])

    # Open-request age as of the extraction snapshot
    is_open = out["case_status"].eq("OPEN")
    age_hours = (snapshot_utc - raw_opened).dt.total_seconds() / 3600
    out["open_age_hours"] = age_hours.where(is_open)

    # Rule 4: Category null -> 'Unknown' (original kept alongside)
    out["category_source"] = df["Category"]
    out["category"] = df["Category"].fillna("Unknown")
    out["category_was_missing"] = df["Category"].isna()

    out["department"] = df["Department"]
    out["reason_name"] = df["ReasonName"]
    out["type_name"] = df["TypeName"]

    # Rule 6: normalize source channel, keep original
    out["source_id_original"] = df["SourceID"]
    out["source_channel"] = normalize_source(df["SourceID"])

    # Descriptions: preserve nulls, add a flag. Contains addresses, so treat as sensitive.
    out["object_description"] = df["ObjectDescription"]
    out["has_description"] = df["ObjectDescription"].notna()

    # Geography (projected coordinates; lon/lat conversion comes after CRS verification)
    out["council_district"] = df["CouncilDistrict"]
    out["x_coord"] = df["XCOORD"]
    out["y_coord"] = df["YCOORD"]
    out["geometry_x"] = df["geometry_x"]
    out["geometry_y"] = df["geometry_y"]

    # Rule 7: ReportStartingDate / ReportEndingDate are intentionally not carried over.
    return out


# --------------------------------------------------
# 3. Validation
# --------------------------------------------------
def validate(raw, curated, manifest):
    checks = {}
    checks["raw_rows"] = len(raw)
    checks["curated_rows"] = len(curated)
    checks["manifest_expected_rows"] = manifest["expected_records"]
    checks["rows_reconcile"] = len(raw) == len(curated) == manifest["expected_records"]
    checks["case_id_unique"] = bool(curated["case_id"].is_unique)
    checks["invalid_close_date_count"] = int(curated["invalid_close_date"].sum())
    checks["negative_duration_count"] = int(curated["negative_duration"].sum())
    checks["invalid_sla_date_count"] = int(curated["invalid_sla_date"].sum())
    checks["category_unknown_count"] = int((curated["category"] == "Unknown").sum())
    checks["valid_resolution_count"] = int(curated["is_valid_resolution"].sum())
    checks["open_count"] = int(curated["case_status"].eq("OPEN").sum())
    checks["open_with_age"] = int(curated["open_age_hours"].notna().sum())
    checks["resolution_hours_min"] = float(curated["resolution_hours"].min())
    checks["resolution_hours_median"] = float(curated["resolution_hours"].median())
    checks["resolution_hours_max"] = float(curated["resolution_hours"].max())
    checks["negative_resolution_values"] = int((curated["resolution_hours"] < 0).sum())
    checks["xcoord_equals_geometry_x"] = float(
        (curated["x_coord"] == curated["geometry_x"].round()).mean()
    )
    checks["source_channels"] = curated["source_channel"].value_counts().to_dict()

    # Hard failures
    assert checks["rows_reconcile"], "Row counts do not reconcile"
    assert checks["case_id_unique"], "Duplicate CaseIDs after cleaning"
    assert checks["negative_resolution_values"] == 0, "Negative resolution hours remain"
    assert checks["open_with_age"] == checks["open_count"], "Open cases missing age"
    return checks


# --------------------------------------------------
# 4. Main
# --------------------------------------------------
def main():
    extraction_dir = find_extraction_dir()
    print("Reading:", extraction_dir)

    with open(extraction_dir / "manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Snapshot time comes from the manifest (UTC): 'YYYYMMDD_HHMMSS'
    snapshot_utc = pd.to_datetime(
        manifest["extraction_timestamp_utc"], format="%Y%m%d_%H%M%S", utc=True
    )
    print("Snapshot (UTC):", snapshot_utc)

    raw = load_raw(extraction_dir)
    curated = clean(raw, snapshot_utc)
    checks = validate(raw, curated, manifest)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = OUT_DIR / "311_curated.parquet"
    curated.to_parquet(parquet_path, index=False)

    report = {
        "source_extraction": str(extraction_dir),
        "snapshot_utc": str(snapshot_utc),
        "checks": checks,
    }
    with open(OUT_DIR / "311_curated_reconciliation.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, default=str)

    print("\n--- VALIDATION ---")
    for key, value in checks.items():
        print(f"{key}: {value}")
    print("\nCurated columns:", len(curated.columns))
    print("Written:", parquet_path)


if __name__ == "__main__":
    main()
