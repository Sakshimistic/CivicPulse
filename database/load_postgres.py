"""
Create the CivicPulse warehouse schema and load the enriched 311 data into PostgreSQL.

Run from the civicpulse folder:
    python database/load_postgres.py

Uses the psql command-line client that ships with PostgreSQL (no extra Python package).
Connection settings come from a .env file (see .env.example). The script is idempotent:
it drops and recreates the `civicpulse` schema and reloads everything in one transaction.
object_description (address text) is intentionally NOT loaded into the warehouse.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

SCHEMA_FILE = Path("database/schema.sql")
DATA_FILE = Path("data/processed/311/311_enriched.parquet")
RAW_ROOT = Path("data/raw/311")

CHANNEL_LABELS = {
    "voice_in": "Phone (inbound)", "voice_out": "Phone (outbound)", "web": "Web",
    "wom": "WOM", "face_to_face": "Face to face", "email_in": "Email (inbound)",
    "email_out": "Email (outbound)",
}


# ---------------------------------------------------------------- psql helpers
def find_psql():
    found = shutil.which("psql")
    if found:
        return found
    for path in sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin/psql.exe"), reverse=True):
        return str(path)
    sys.exit("psql not found. Install PostgreSQL or add its bin folder to PATH.")


PSQL = find_psql()
DBNAME = os.getenv("PGDATABASE", "civicpulse")


def psql_env():
    if not os.getenv("PGPASSWORD"):
        sys.exit("PGPASSWORD is not set. Copy .env.example to .env and fill it in.")
    env = os.environ.copy()
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5432")
    env.setdefault("PGUSER", "postgres")
    return env


def run_psql(args, dbname, stdin_text=None):
    cmd = [PSQL, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", dbname, *args]
    result = subprocess.run(cmd, env=psql_env(), input=stdin_text, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"psql failed:\n{result.stderr}")
    return result.stdout.strip()


def query(dbname, statement):
    return run_psql(["-t", "-A", "-c", statement], dbname)


def ensure_database():
    exists = query("postgres", f"SELECT 1 FROM pg_database WHERE datname = '{DBNAME}'")
    if not exists:
        run_psql(["-c", f'CREATE DATABASE "{DBNAME}"'], "postgres")
        print("Created database:", DBNAME)


# ---------------------------------------------------------------- dimension builders
def build_dim_date(start, end):
    days = pd.date_range(start, end, freq="D")
    return pd.DataFrame({
        "date_key": days.strftime("%Y%m%d").astype(int),
        "full_date": days.strftime("%Y-%m-%d"),
        "year": days.year,
        "quarter": days.quarter,
        "month": days.month,
        "month_name": days.strftime("%B"),
        "year_month": days.strftime("%Y-%m"),
        "day_of_month": days.day,
        "iso_weekday": days.dayofweek + 1,
        "weekday_name": days.strftime("%A"),
        "is_weekend": days.dayofweek >= 5,
    })


def write_csv(frame, folder, name):
    path = folder / f"{name}.csv"
    frame.to_csv(path, index=False, na_rep="\\N")
    return path


def copy_command(table, columns, path):
    cols = ", ".join(columns)
    posix = path.as_posix()
    return f"\\copy civicpulse.{table} ({cols}) FROM '{posix}' WITH (FORMAT csv, HEADER true, NULL '\\N')\n"


def main():
    df = pd.read_parquet(DATA_FILE)
    print("Rows to load:", len(df))

    manifest_path = sorted(RAW_ROOT.glob("extraction_*"))[-1] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_ts = pd.to_datetime(manifest["extraction_timestamp_utc"], format="%Y%m%d_%H%M%S", utc=True)
    # Layer's ReportStartingDate (2025-11-07), as local midnight; matches in_report_window in clean_311.py
    window_start = pd.Timestamp("2025-11-07", tz="America/Chicago")

    # Date keys use LOCAL dates so a 23:30 request stays on its own day.
    df["opened_date_key"] = df["opened_local"].dt.strftime("%Y%m%d").astype(int)
    df["closed_date_key"] = pd.to_numeric(df["closed_local"].dt.strftime("%Y%m%d"), errors="coerce").astype("Int64")

    # Dimensions with explicit surrogate keys
    date_start = min(df["opened_local"].min(), df["closed_local"].min()).date()
    date_end = (max(df["closed_local"].max(), df["opened_local"].max()) + pd.Timedelta(days=45)).date()
    dim_date = build_dim_date(date_start, date_end)

    dim_department = pd.DataFrame({"department_name": sorted(df["department"].unique())})
    dim_department.insert(0, "department_key", range(1, len(dim_department) + 1))

    dim_issue = (df[["category", "reason_name", "type_name"]].drop_duplicates()
                 .sort_values(["category", "reason_name", "type_name"]).reset_index(drop=True))
    dim_issue.insert(0, "issue_type_key", range(1, len(dim_issue) + 1))

    dim_district = pd.DataFrame({"district_key": sorted(df["council_district"].unique())})
    dim_district["district_label"] = dim_district["district_key"].map(
        lambda d: "Unassigned" if d == 0 else f"District {d}")
    dim_district["is_assigned"] = dim_district["district_key"] != 0

    dim_channel = pd.DataFrame({"channel_code": sorted(df["source_channel"].unique())})
    dim_channel.insert(0, "channel_key", range(1, len(dim_channel) + 1))
    dim_channel["channel_label"] = dim_channel["channel_code"].map(CHANNEL_LABELS).fillna(dim_channel["channel_code"])

    # Fact table keys
    df["department_key"] = df["department"].map(dict(zip(dim_department["department_name"], dim_department["department_key"])))
    df["channel_key"] = df["source_channel"].map(dict(zip(dim_channel["channel_code"], dim_channel["channel_key"])))
    issue_map = {(r.category, r.reason_name, r.type_name): r.issue_type_key for r in dim_issue.itertuples()}
    df["issue_type_key"] = [issue_map[k] for k in zip(df["category"], df["reason_name"], df["type_name"])]
    df["district_key"] = df["council_district"]

    fact_cols = {
        "case_id": "case_id", "objectid": "objectid",
        "opened_date_key": "opened_date_key", "closed_date_key": "closed_date_key",
        "department_key": "department_key", "issue_type_key": "issue_type_key",
        "district_key": "district_key", "channel_key": "channel_key",
        "opened_ts": "opened_utc", "closed_ts": "closed_utc", "sla_ts": "sla_utc",
        "opened_hour": "opened_hour", "case_status": "case_status",
        "is_late_source": "is_late_source", "resolution_hours": "resolution_hours",
        "is_valid_resolution": "is_valid_resolution", "invalid_close_date": "invalid_close_date",
        "negative_duration": "negative_duration", "invalid_sla_date": "invalid_sla_date",
        "category_was_missing": "category_was_missing", "has_description": "has_description",
        "in_report_window": "in_report_window", "latitude": "latitude", "longitude": "longitude",
        "x_coord": "x_coord", "y_coord": "y_coord",
    }
    fact = df[list(fact_cols.values())].rename(columns={v: k for k, v in fact_cols.items()})

    ensure_database()

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        script = ["\\set ON_ERROR_STOP on\n", "BEGIN;\n", SCHEMA_FILE.read_text(encoding="utf-8"), "\n"]
        for table, frame in [
            ("dim_date", dim_date), ("dim_department", dim_department), ("dim_issue_type", dim_issue),
            ("dim_council_district", dim_district), ("dim_source_channel", dim_channel),
            ("fact_service_request", fact),
        ]:
            script.append(copy_command(table, list(frame.columns), write_csv(frame, folder, table)))

        script.append(
            "INSERT INTO civicpulse.etl_load_log (source_file, snapshot_ts, fact_rows, window_start_ts) VALUES "
            f"('{DATA_FILE.as_posix()}', '{snapshot_ts.isoformat()}', {len(fact)}, '{window_start.isoformat()}');\n"
        )
        # Keep serial sequences ahead of the explicit keys we loaded
        for table, key in [("dim_department", "department_key"), ("dim_issue_type", "issue_type_key"),
                           ("dim_source_channel", "channel_key")]:
            script.append(f"SELECT setval(pg_get_serial_sequence('civicpulse.{table}', '{key}'), "
                          f"(SELECT max({key}) FROM civicpulse.{table}));\n")
        script.append("COMMIT;\n")
        run_psql([], DBNAME, stdin_text="".join(script))

    # Reconciliation
    loaded = int(query(DBNAME, "SELECT count(*) FROM civicpulse.fact_service_request"))
    open_n = int(query(DBNAME, "SELECT count(*) FROM civicpulse.fact_service_request WHERE case_status = 'OPEN'"))
    median_sql = float(query(
        DBNAME,
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) "
        "FROM civicpulse.fact_service_request WHERE is_valid_resolution AND in_report_window"))
    median_pd = float(df.loc[df["is_valid_resolution"] & df["in_report_window"], "resolution_hours"].median())
    problems = []
    if loaded != len(df):
        problems.append(f"Loaded {loaded} rows, expected {len(df)}")
    if open_n != int((df["case_status"] == "OPEN").sum()):
        problems.append("Open count mismatch")
    if abs(median_sql - median_pd) > 1e-3:
        problems.append(f"Median mismatch: SQL {median_sql} vs pandas {median_pd}")
    if problems:
        sys.exit("RECONCILIATION FAILED: " + "; ".join(problems))

    print("Loaded fact rows:", loaded)
    print("Open requests:", open_n)
    print(f"Median resolution hours (window cohort): SQL {median_sql:.3f} | pandas {median_pd:.3f}")
    for table in ("dim_date", "dim_department", "dim_issue_type", "dim_council_district", "dim_source_channel"):
        print(table, query(DBNAME, f"SELECT count(*) FROM civicpulse.{table}"))


if __name__ == "__main__":
    main()
