import json
import pandas as pd

from pathlib import Path


DATA_DIR = Path("data/raw/311/extraction_20261113_215950")

# --------------------------------------------------
# Load all batches (attributes only)
# --------------------------------------------------
records = []
for file_path in sorted(DATA_DIR.glob("batch_*.json")):
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    for feature in data["features"]:
        records.append(feature["attributes"])

df = pd.DataFrame(records)

date_columns = [
    "OpenedDateTime",
    "ClosedDateTime",
    "SLADate",
    "ReportStartingDate",
    "ReportEndingDate",
]
for column in date_columns:
    df[column] = pd.to_datetime(df[column], unit="ms", utc=True, errors="coerce")

print("Rows loaded:", len(df))


# --------------------------------------------------
# 1. Are ALL 782 negative durations the 1900 placeholder?
# --------------------------------------------------
print("\n--- 1. NEGATIVE DURATIONS vs 1900 PLACEHOLDER ---")

neg = df[df["ClosedDateTime"].notna() & (df["ClosedDateTime"] < df["OpenedDateTime"])]
placeholder_close = df["ClosedDateTime"].dt.year == 1900

print("Negative durations:", len(neg))
print("  ...of which closed date year is 1900:", (neg["ClosedDateTime"].dt.year == 1900).sum())
print("  ...NOT 1900 (genuine negatives):", (neg["ClosedDateTime"].dt.year != 1900).sum())
print("All records with 1900 close date:", placeholder_close.sum())

print("\nDistinct close dates among negatives:")
print(neg["ClosedDateTime"].value_counts().head(10))

print("\nNegatives by opened year-month:")
print(neg["OpenedDateTime"].dt.to_period("M").value_counts().sort_index())

print("\nNegatives by department:")
print(neg["Department"].value_counts())

genuine = neg[neg["ClosedDateTime"].dt.year != 1900]
if len(genuine):
    print("\nGenuine (non-1900) negatives, first 20:")
    print(
        genuine[["CaseID", "OpenedDateTime", "ClosedDateTime", "Department", "TypeName"]]
        .head(20)
        .to_string(index=False)
    )


# --------------------------------------------------
# 2. Other placeholder / implausible dates in every date column
# --------------------------------------------------
print("\n--- 2. DATE RANGE PER COLUMN ---")

for column in date_columns:
    s = df[column]
    print(
        f"{column}: min={s.min()}  max={s.max()}  "
        f"null={s.isna().sum()}  year<2000={(s.dt.year < 2000).sum()}  "
        f"year>2026={(s.dt.year > 2026).sum()}"
    )

print("\nClosed dates AFTER the extraction time (future):")
print((df["ClosedDateTime"] > pd.Timestamp("2026-11-13", tz="UTC")).sum())


# --------------------------------------------------
# 3. Can missing categories be recovered from TypeName?
# --------------------------------------------------
print("\n--- 3. MISSING CATEGORY RECOVERY ---")

missing_cat = df[df["Category"].isna()]
print("Missing categories:", len(missing_cat))
print("\nTypeName of missing-category rows:")
print(missing_cat["TypeName"].value_counts())

known = df[df["Category"].notna()]
print("\nFor those same TypeNames, which Category do other rows have?")
for type_name in missing_cat["TypeName"].unique():
    cats = known.loc[known["TypeName"] == type_name, "Category"].value_counts()
    print(f"\n{type_name}")
    print(cats.to_string() if len(cats) else "  (no other rows with this TypeName -> cannot recover)")

print("\nMissing-category rows by opened year:")
print(missing_cat["OpenedDateTime"].dt.year.value_counts().sort_index())


# --------------------------------------------------
# 4. Are missing descriptions concentrated anywhere?
# --------------------------------------------------
print("\n--- 4. MISSING DESCRIPTION RATE ---")

df["desc_missing"] = df["ObjectDescription"].isna()

print("\nBy category (rate %):")
print((df.groupby("Category", dropna=False)["desc_missing"].mean() * 100).round(1).sort_values(ascending=False))

print("\nBy source channel (rate %):")
print((df.groupby("SourceID", dropna=False)["desc_missing"].agg(["mean", "size"])
       .assign(mean=lambda x: (x["mean"] * 100).round(1))
       .sort_values("size", ascending=False)
       .head(10)))

print("\nBy opened year (rate %):")
print((df.groupby(df["OpenedDateTime"].dt.year)["desc_missing"].mean() * 100).round(1))


# --------------------------------------------------
# 5. SLA / Late fields (meaning still unverified)
# --------------------------------------------------
print("\n--- 5. SLA FIELDS ---")

print(df["LateYesNo"].value_counts(dropna=False))
print("\nSLADate missing:", df["SLADate"].isna().sum())

valid = df[df["ClosedDateTime"].notna() & (df["ClosedDateTime"].dt.year > 1900) & df["SLADate"].notna()].copy()
valid["closed_after_sla"] = valid["ClosedDateTime"] > valid["SLADate"]
print("\nDoes LateYesNo agree with (ClosedDateTime > SLADate) on closed cases?")
print(pd.crosstab(valid["LateYesNo"], valid["closed_after_sla"], margins=True))

print("\nReportStartingDate / ReportEndingDate distinct values:")
print(df["ReportStartingDate"].value_counts().head(5))
print(df["ReportEndingDate"].value_counts().head(5))

print("\nInvestigation part 2 completed!")
