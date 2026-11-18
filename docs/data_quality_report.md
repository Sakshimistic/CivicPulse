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
| Opened range | 2020-10-30 to 2026-11-06 (97.5% opened on or after 2025-11-07, see 2.8) |
| OPEN / CLOSED | 25,411 / 485,124 |
| Missing coordinates | 0 |

The profiler printed 20 columns and saved 25 in its summary. The extra 5 are the `*_converted` datetime columns added after the print. This is not a data issue.

## 2. Issues and decisions

### 2.1 Placeholder close date (`1900-01-01`)
- **Finding:** 782 records have `ClosedDateTime < OpenedDateTime`. 780 have a close date of `1900-01-01 00:00:00 UTC`. 2 are genuine negatives (Public Works, opened 2026-06 and 2026-08, closed hours to days earlier).
- **Pattern:** the 780 were all opened between 2025-11-07 and 2025-12-18, the first six weeks of the layer's reporting window (see 2.8). Development Services accounts for 679. Cause is unknown. It is likely a system or process artifact tied to when the window begins.
- **Status:** all 780 are marked CLOSED, so they pass the status/close-date consistency check. That check does not detect them.
- **Decision:**
  - Set the 1900 close date to NULL and flag `invalid_close_date`.
  - Flag the 2 genuine negatives `negative_duration`.
  - Exclude all 782 from resolution metrics. Keep the rows.
  - Do not reclassify their status. It stays CLOSED as in the source.
- **Unresolved:** why the placeholder appears only in requests opened in the first six weeks of the window.

### 2.2 Missing `Category` (220)
- **Finding:** all opened in 2026. 218 are `Parks Internal (Ballfield Maintenance)`, 1 `Sanitation (Natural Areas-Mowing)`, 1 `Dart Preliminary Inspection`. Department is Parks and Recreation; `ReasonName` is blank.
- **Recovery:** none of these `TypeName` values occur on any row with a category, so the category cannot be inferred from the data.
- **Decision:** set the curated category to `Unknown`. Preserve the original null in the raw field. A manual mapping (for example, ballfield maintenance to `Parks`) may be added only as a documented, analyst-assigned mapping.

### 2.3 Missing `ObjectDescription` (34,284, 6.72%)
- **Finding:** the missing rate falls over time within the reporting window: 20% of requests opened Nov 2025, 13% Dec, 11% Jan, 10% Mar, 6% Apr, then about 1% from May 2026 on. By channel, `WOM` is 33% missing; every other channel is below 1%. By category, Property Maintenance (17%) and Graffiti (13%) are the highest.
- **Correction:** an earlier version of this report said older descriptions looked purged, based on rates by year. That was wrong. Rows opened before 2025 are only a few hundred survivors of the window (see 2.8), so their rates were not meaningful. The real pattern is a gap concentrated in early-window months, the `WOM` channel, and two categories. The cause is unknown.
- **Decision:** keep nulls, do not impute. Check completeness before any text analysis. Records remain usable because coordinates are complete.

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

### 2.8 The layer is a rolling one-year window, not full history
- **Finding:** every valid close date in the layer is on or after 2025-11-07, which equals `ReportStartingDate`. `ReportEndingDate` is 2026-11-06. So the layer holds requests that were closed inside that window, plus everything still open.
- **Consequence:** 497,550 requests (97.5%) were opened on or after 2025-11-07 and are fully represented. The other 12,985 were opened earlier (2020 to 2025-11-06) and appear only because they closed inside the window (12,596) or are still open (389). They are a biased survivor set, and monthly counts before Nov 2025 are not real demand.
- **Effect on analysis:**
  - Volume, category mix and resolution analysis use the window cohort (opened on or after 2025-11-07).
  - The 12,985 earlier requests stay in the data and count toward the open backlog.
  - Multi-year trends and year-over-year comparisons are not possible from this layer. Seasonality is limited to one year.
  - Resolution times for the newest requests are biased short, because slow cases are still open (44% of November 2026 requests are open). Resolution metrics therefore use requests opened at least 3 months before the snapshot (before 2026-08-01).
- **Earlier statements corrected:** the "2020-10-30 to 2026-11-06" coverage in the handoff and earlier drafts describes the oldest and newest survivors, not the dataset's real span.
- **Update cadence:** the layer reports a `dataLastEditDate` of 2026-11-15, two days after our extraction, so the data is changing. The refresh frequency still needs observing over several extractions.
- **Decision:** keep all rows. The cleaning step adds `in_report_window` (opened on or after 2025-11-07 local).

### 2.9 Timestamps are local time stored as UTC (inference)
- **Finding:** read as UTC, requests would peak at 3 to 10am Central, with the sharpest rise in the middle of the night. Read as San Antonio wall-clock time, requests ramp up at 07:00 to 08:00 and peak at 10:00, with the quietest hours overnight, which is what a business-hours call centre looks like. The web channel and close times follow the same daytime curve.
- **Caveat:** the layer metadata contains no time-zone information, so this is an inference from the diurnal pattern.
- **Decision:** relabel raw timestamps as `America/Chicago` and derive true UTC from them (`RAW_TIMES_ARE_LOCAL` in `clean_311.py`). Resolution durations are unaffected except across daylight-saving changes. The earlier curated files, which assumed true UTC, were regenerated.

### 2.10 Council district 0
- **Finding:** 82,704 cohort requests (16.6%) have `CouncilDistrict = 0`. 96% are Development Services (code compliance), mostly overgrown yards, bandit signs and graffiti. Their open share is 11.9% against 2.6 to 4.6% in districts 1 to 10, and their median resolution is 218 hours against 29 to 47 hours.
- **Interpretation:** 0 likely means "not assigned a district" and is not a real district. Its coordinates fall inside the San Antonio area.
- **Decision:** do not treat 0 as a district in district comparisons. Show it separately as "Unassigned". Validate with the official boundary layer when GIS data is added.

## 3. Open questions
1. Why the `1900-01-01` placeholder appears only for requests opened in the first six weeks of the window.
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
8. Treat raw timestamps as San Antonio local wall-clock time. Derive true UTC from them and keep local time (see 2.9).
9. Keep all 510,535 rows. Nothing is deleted.
10. Analyse volume and resolution on the window cohort only (see 2.8). The curated data flags it as `in_report_window`.
11. Do not treat `CouncilDistrict = 0` as a district (see 2.10).
