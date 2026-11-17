
import json
import pandas as pd

from pathlib import Path


# --------------------------------------------------
# 1. Configure extraction directory
# --------------------------------------------------

EXTRACTION_DIR = Path(
    "data/raw/311/extraction_20261113_215950"
)

REPORT_DIR = Path("data/interim/311_profile")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. Load extraction manifest
# --------------------------------------------------

with open(
    EXTRACTION_DIR / "manifest.json",
    "r",
    encoding="utf-8"
) as file:
    manifest = json.load(file)

print("Expected records:", manifest["expected_records"])


# --------------------------------------------------
# 3. Read all JSON batches
# --------------------------------------------------

print("\nLoading JSON files...")

records = []

batch_files = sorted(
    EXTRACTION_DIR.glob("batch_*.json")
)

for batch_file in batch_files:

    with open(batch_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    for feature in data.get("features", []):

        attributes = feature.get("attributes", {})
        geometry = feature.get("geometry") or {}

        # Combine attributes and geometry
        record = attributes.copy()

        record["geometry_x"] = geometry.get("x")
        record["geometry_y"] = geometry.get("y")

        records.append(record)

print("Batches read:", len(batch_files))

# Convert records into a DataFrame
df = pd.DataFrame(records)

print("Total rows loaded:", len(df))
print("Total columns:", len(df.columns))


# --------------------------------------------------
# 4. Check duplicate records and identifiers
# --------------------------------------------------

print("\n--- DUPLICATE CHECKS ---")

print(
    "Duplicate OBJECTIDs:",
    df["OBJECTID"].duplicated().sum()
)

print(
    "Duplicate CaseIDs:",
    df["CaseID"].duplicated().sum()
)

print(
    "Completely duplicate rows:",
    df.duplicated().sum()
)


# --------------------------------------------------
# 5. Check missing values
# --------------------------------------------------

print("\n--- MISSING VALUES ---")

missing = pd.DataFrame({
    "missing_count": df.isnull().sum(),
    "missing_percentage": (
        df.isnull().mean() * 100
    ).round(2)
})

missing = missing.sort_values(
    "missing_percentage",
    ascending=False
)

print(missing)

missing.to_csv(
    REPORT_DIR / "missing_values.csv"
)


# --------------------------------------------------
# 6. Convert date columns
# --------------------------------------------------

date_columns = [
    "OpenedDateTime",
    "ClosedDateTime",
    "SLADate",
    "ReportStartingDate",
    "ReportEndingDate"
]

for column in date_columns:

    df[column + "_converted"] = pd.to_datetime(
        df[column],
        unit="ms",
        errors="coerce",
        utc=True
    )


# --------------------------------------------------
# 7. Analyze request dates
# --------------------------------------------------

print("\n--- DATE ANALYSIS ---")

opened = df["OpenedDateTime_converted"]
closed = df["ClosedDateTime_converted"]

print("Oldest request:", opened.min())
print("Newest request:", opened.max())

print(
    "Missing or invalid opening dates:",
    opened.isna().sum()
)

print(
    "Missing or invalid closing dates:",
    closed.isna().sum()
)

print(
    "Closed before opened:",
    (closed.notna() & opened.notna() & (closed < opened)).sum()
)

print(
    "Open requests with closing dates:",
    (
        (df["CaseStatus"] == "OPEN")
        & closed.notna()
    ).sum()
)

print(
    "Closed requests without closing dates:",
    (
        (df["CaseStatus"] == "CLOSED")
        & closed.isna()
    ).sum()
)


# --------------------------------------------------
# 8. Analyze request statuses
# --------------------------------------------------

print("\n--- STATUS DISTRIBUTION ---")

status_counts = df["CaseStatus"].value_counts(
    dropna=False
)

print(status_counts)

status_counts.to_csv(
    REPORT_DIR / "status_counts.csv"
)


# --------------------------------------------------
# 9. Analyze categories and departments
# --------------------------------------------------

print("\n--- TOP REQUEST CATEGORIES ---")

category_counts = df["Category"].value_counts(
    dropna=False
)

print(category_counts.head(15))

category_counts.to_csv(
    REPORT_DIR / "category_counts.csv"
)


print("\n--- TOP DEPARTMENTS ---")

department_counts = df["Department"].value_counts(
    dropna=False
)

print(department_counts.head(15))

department_counts.to_csv(
    REPORT_DIR / "department_counts.csv"
)


# --------------------------------------------------
# 10. Geographic data checks
# --------------------------------------------------

print("\n--- GEOGRAPHIC CHECKS ---")

print(
    "Missing X coordinates:",
    df["XCOORD"].isna().sum()
)

print(
    "Missing Y coordinates:",
    df["YCOORD"].isna().sum()
)

print(
    "Missing geometry X:",
    df["geometry_x"].isna().sum()
)

print(
    "Missing geometry Y:",
    df["geometry_y"].isna().sum()
)


# --------------------------------------------------
# 11. Save overall profiling summary
# --------------------------------------------------

summary = {
    "total_rows": len(df),
    "total_columns": len(df.columns),
    "expected_rows": manifest["expected_records"],
    "objectid_duplicates": int(
        df["OBJECTID"].duplicated().sum()
    ),
    "caseid_duplicates": int(
        df["CaseID"].duplicated().sum()
    ),
    "duplicate_rows": int(df.duplicated().sum()),
    "missing_opened_dates": int(opened.isna().sum()),
    "missing_closed_dates": int(closed.isna().sum()),
    "closed_before_opened": int(
        (
            closed.notna()
            & opened.notna()
            & (closed < opened)
        ).sum()
    ),
    "oldest_request": str(opened.min()),
    "newest_request": str(opened.max())
}

with open(
    REPORT_DIR / "profiling_summary.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(summary, file, indent=4)


print("\n--------------------------------")
print("DATA PROFILING COMPLETED")
print("--------------------------------")
print("Report directory:", REPORT_DIR)
print("Summary:", summary)
