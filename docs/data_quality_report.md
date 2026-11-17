# Data Quality Report: San Antonio 311 All Service Calls

**Snapshot:** extraction `20261113_215950` (510,535 records, 256 batches, manifest status SUCCESS)
**Source:** City of San Antonio 311 ArcGIS Feature Service, layer 0
**Scripts:** `ingestion/profile_311.py`, `ingestion/investigate_311.py`, `ingestion/investigate_311_part2.py`
**Status:** Investigation complete. Cleaning not yet implemented. Raw data is unmodified.

## 1. Reconciliation

| Check | Result |
|---|---|
| Records expected / downloaded | 510,535 / 510,535 |
| Duplicate `OBJECTID`, `CaseID`, full rows | 0 / 0 / 0 |
| Opened range | 2020-10-30 to 2026-11-06 (UTC) |
| OPEN / CLOSED | 25,411 / 485,124 |
| Missing coordinates | 0 |

The profiler printed 20 columns and saved 25 in its summary. The extra 5 are the `*_converted` datetime columns added after the print. This is not a data issue.

## 2. Issues and decisions

### 2.1 Placeholder close date (`1900-01-01`)
- **Finding:** 782 records have `ClosedDateTime < OpenedDateTime`. 780 have a close date of `1900-01-01 00:00:00 UTC`. 2 are genuine negatives (Public Works, opened 2026-06 and 2026-08, closed hours to days earlier).
- **Pattern:** the 780 were all opened in Nov–Dec 2025 (337 and 443). Development Services accounts for 679. Cause is unknown. It is likely a system or process artifact.
- **Status:** all 780 are marked CLOSED, so they pass the status/close-date consistency check. That check does not detect them.
- **Decision:**
  - Set the 1900 close date to NULL and flag `invalid_close_date`.
  - Flag the 2 genuine negatives `negative_duration`.
  - Exclude all 782 from resolution metrics. Keep the rows.
  - Do not reclassify their status. It stays CLOSED as in the source.
- **Unresolved:** why the placeholder appears only in Nov–Dec 2025.

### 2.2 Missing `Category` (220)
- **Finding:** all opened in 2026. 218 are `Parks Internal (Ballfield Maintenance)`, 1 `Sanitation (Natural Areas-Mowing)`, 1 `Dart Preliminary Inspection`. Department is Parks and Recreation; `ReasonName` is blank.
- **Recovery:** none of these `TypeName` values occur on any row with a category, so the category cannot be inferred from the data.
- **Decision:** set the curated category to `Unknown`. Preserve the original null in the raw field. A manual mapping (for example, ballfield maintenance to `Parks`) may be added only as a documented, analyst-assigned mapping.

### 2.3 Missing `ObjectDescription` (34,284, 6.72%)
- **Finding:** the missing rate depends on record age: 2021 100%, 2022 93%, 2023 76%, 2024 54%, 2025 22%, 2026 4%. By channel, `WOM` is 38% missing (85k rows); the other channels are below 3%.
- **Interpretation:** descriptions appear to be removed or not retained for older records. This is not a random defect. (Inference from the pattern; not confirmed with the source owner.)
- **Decision:** keep nulls, do not impute. Do not plan text analysis or embeddings on older records. Records remain usable because coordinates are complete.

### 2.4 SLA fields
- **Finding:** `LateYesNo = YES` means closed after `SLADate` in all 40,899 closed cases. The reverse is not true: 12,283 closed-after-SLA cases are marked `NO`. 15,043 of the 55,942 `YES` records are not in the closed-with-valid-dates group, so they are probably open cases past their SLA date.
- **Placeholder:** 537 `SLADate` values are 1899/1900. 18,597 are dated after 2026 (normal for open cases; max 2028-04).
- **Decision:** report lateness using the source `LateYesNo` as given. Do not recompute it from `SLADate`. Set the 1899/1900 `SLADate` values to NULL.
- **Unresolved:** why 12,283 late closures are marked `NO` (grace period, paused SLA or a different basis).

### 2.5 `ReportStartingDate` / `ReportEndingDate`
- **Finding:** constant on every row (2025-11-07 and 2026-11-06). These are layer-level report-window metadata and not request attributes.
- **Decision:** drop from the curated layer.

### 2.6 `SourceID` inconsistent casing
- **Finding:** `voice_in` / `Voice in`, `web` / `Web`, `voice_out` / `Voice out`, `email_in` / `email_out`, plus `WOM` and `Face to face`.
- **Decision:** normalize casing and separators into one value per channel. Keep the original in the raw field.

### 2.7 Status vs close date
- 485,124 CLOSED have a close date and 25,411 OPEN have none. No contradictions. (Note the caveat in 2.1.)

## 3. Open questions
1. Why the `1900-01-01` placeholder appears only for Nov–Dec 2025 requests.
2. The exact meaning of `SLADate` and `LateYesNo`.
3. The CRS and units of `XCOORD`/`YCOORD` (reported WKID 102740 / 2278). Verify before converting to lon/lat.
4. Whether the dataset covers all 311 channels (do not make citywide claims yet).

## 4. Rules for the cleaning script
1. `ClosedDateTime` = 1900-01-01 becomes NULL, with flag `invalid_close_date`.
2. `ClosedDateTime < OpenedDateTime` (other) is flagged `negative_duration`.
3. Resolution metrics use only closed records where neither flag is set.
4. `Category` null becomes `Unknown`. The source value is preserved.
5. `SLADate` placeholders (year < 2000) become NULL.
6. `SourceID` is normalized.
7. Drop `ReportStartingDate` and `ReportEndingDate`.
8. Preserve UTC timestamps and derive `America/Chicago` local fields.
9. Keep all 510,535 rows. Nothing is deleted.
