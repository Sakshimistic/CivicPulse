import json
import pandas as pd

from pathlib import Path


# Location of our extracted data
DATA_DIR = Path(
    "data/raw/311/extraction_20261113_215950"
)

records = []

# Load all extracted batches
for file_path in sorted(DATA_DIR.glob("batch_*.json")):

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    for feature in data["features"]:

        attributes = feature["attributes"]

        records.append(attributes)


# Convert to DataFrame
df = pd.DataFrame(records)

# Convert date columns from milliseconds to UTC datetime
date_columns = [
    "OpenedDateTime",
    "ClosedDateTime",
    "SLADate"
]

for column in date_columns:

    df[column] = pd.to_datetime(
        df[column],
        unit="ms",
        utc=True,
        errors="coerce"
    )


# 1. Investigate closed-before-opened records
print("\n--- CLOSED BEFORE OPENED ---")

anomalies = df[
    (df["ClosedDateTime"].notna()) &
    (df["ClosedDateTime"] < df["OpenedDateTime"])
]

print("Total anomalies:", len(anomalies))

print(
    anomalies[
        [
            "CaseID",
            "OpenedDateTime",
            "ClosedDateTime",
            "Department",
            "Category",
            "TypeName",
            "CaseStatus"
        ]
    ].head(20).to_string(index=False)
)


# 2. Investigate missing categories
print("\n--- MISSING CATEGORIES ---")

missing_categories = df[df["Category"].isna()]

print("Total:", len(missing_categories))

print(
    missing_categories[
        ["CaseID", "Department", "ReasonName", "TypeName"]
    ].head(20).to_string(index=False)
)


# 3. Investigate missing descriptions
print("\n--- MISSING DESCRIPTIONS ---")

missing_descriptions = df[
    df["ObjectDescription"].isna()
]

print("Total:", len(missing_descriptions))

print(
    missing_descriptions[
        ["CaseID", "Category", "Department", "TypeName"]
    ].head(20).to_string(index=False)
)


# 4. Check request statuses
print("\n--- STATUS VALIDATION ---")

print(
    pd.crosstab(
        df["CaseStatus"],
        df["ClosedDateTime"].isna(),
        margins=True
    )
)


print("\nInvestigation completed!")
