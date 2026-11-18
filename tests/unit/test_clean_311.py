"""
Unit tests for transformations/pandas/clean_311.py.

The module is loaded by file path because its folder is named 'pandas',
which would clash with the real pandas package if added to sys.path.
Run from the civicpulse folder:  python -m pytest tests -v
"""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "transformations" / "pandas" / "clean_311.py"
spec = importlib.util.spec_from_file_location("clean_311", MODULE_PATH)
clean_311 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clean_311)

SNAPSHOT = pd.Timestamp("2026-11-13 21:59:50", tz="UTC")


def ms(text):
    """'2026-01-01 12:00' (UTC) -> Unix milliseconds, as the API returns."""
    return int(pd.Timestamp(text, tz="UTC").timestamp() * 1000)


def make_row(**overrides):
    row = {
        "OBJECTID": 1,
        "CaseID": 100,
        "Category": "Animals",
        "OpenedDateTime": ms("2026-01-01 12:00"),
        "ClosedDateTime": ms("2026-01-02 12:00"),
        "SLADate": ms("2026-01-05 12:00"),
        "LateYesNo": "NO",
        "Department": "Animal Care Services",
        "ReasonName": "Stray",
        "TypeName": "Animals(Stray Animal)",
        "CaseStatus": "CLOSED",
        "SourceID": "Voice in",
        "ObjectDescription": "123 Main St",
        "CouncilDistrict": 1,
        "XCOORD": 2100000,
        "YCOORD": 13700000,
        "geometry_x": 2100000.4,
        "geometry_y": 13700000.4,
    }
    row.update(overrides)
    return row


def run(*rows):
    return clean_311.clean(pd.DataFrame(rows), SNAPSHOT)


def test_row_count_preserved():
    out = run(make_row(CaseID=1), make_row(CaseID=2), make_row(CaseID=3))
    assert len(out) == 3


def test_normal_closed_case_resolution_hours():
    out = run(make_row())
    assert out.loc[0, "resolution_hours"] == pytest.approx(24.0)
    assert bool(out.loc[0, "is_valid_resolution"])
    assert not out.loc[0, "invalid_close_date"]
    assert not out.loc[0, "negative_duration"]


def test_1900_close_date_is_nulled_and_flagged():
    out = run(make_row(ClosedDateTime=ms("1900-01-01 00:00")))
    assert pd.isna(out.loc[0, "closed_utc"])
    assert bool(out.loc[0, "invalid_close_date"])
    assert not bool(out.loc[0, "is_valid_resolution"])
    assert pd.isna(out.loc[0, "resolution_hours"])
    # Status is left as in the source
    assert out.loc[0, "case_status"] == "CLOSED"


def test_genuine_negative_duration_is_flagged_not_dropped():
    out = run(make_row(ClosedDateTime=ms("2025-12-31 12:00")))
    assert len(out) == 1
    assert bool(out.loc[0, "negative_duration"])
    assert not bool(out.loc[0, "invalid_close_date"])
    assert not bool(out.loc[0, "is_valid_resolution"])
    assert pd.isna(out.loc[0, "resolution_hours"])


def test_open_case_has_age_and_no_resolution():
    out = run(make_row(CaseStatus="OPEN", ClosedDateTime=None, OpenedDateTime=ms("2026-11-12 21:59:50")))
    assert out.loc[0, "open_age_hours"] == pytest.approx(24.0)
    assert pd.isna(out.loc[0, "resolution_hours"])
    assert not bool(out.loc[0, "is_valid_resolution"])


def test_closed_case_has_no_open_age():
    out = run(make_row())
    assert pd.isna(out.loc[0, "open_age_hours"])


def test_missing_category_becomes_unknown_and_source_kept():
    out = run(make_row(Category=None))
    assert out.loc[0, "category"] == "Unknown"
    assert pd.isna(out.loc[0, "category_source"])
    assert bool(out.loc[0, "category_was_missing"])


def test_existing_category_unchanged():
    out = run(make_row(Category="Graffiti"))
    assert out.loc[0, "category"] == "Graffiti"
    assert not bool(out.loc[0, "category_was_missing"])


def test_sla_placeholder_is_nulled_and_flagged():
    out = run(make_row(SLADate=ms("1900-01-01 00:00")))
    assert pd.isna(out.loc[0, "sla_utc"])
    assert bool(out.loc[0, "invalid_sla_date"])


def test_future_sla_date_is_kept():
    out = run(make_row(SLADate=ms("2028-04-19 10:31")))
    assert not bool(out.loc[0, "invalid_sla_date"])
    assert out.loc[0, "sla_utc"].year == 2028


def test_source_channel_is_normalized():
    rows = [
        make_row(CaseID=1, SourceID="Voice in"),
        make_row(CaseID=2, SourceID="voice_in"),
        make_row(CaseID=3, SourceID="Web"),
        make_row(CaseID=4, SourceID="web"),
        make_row(CaseID=5, SourceID="Face to face"),
    ]
    out = run(*rows)
    assert list(out["source_channel"]) == ["voice_in", "voice_in", "web", "web", "face_to_face"]
    assert out.loc[0, "source_id_original"] == "Voice in"


def test_missing_description_preserved_with_flag():
    out = run(make_row(ObjectDescription=None))
    assert pd.isna(out.loc[0, "object_description"])
    assert not bool(out.loc[0, "has_description"])


def test_late_flag_taken_from_source():
    out = run(make_row(CaseID=1, LateYesNo="YES"), make_row(CaseID=2, LateYesNo="NO"))
    assert list(out["is_late_source"]) == [True, False]


def test_local_time_is_america_chicago():
    # 2026-01-01 12:00 UTC is 06:00 in Chicago (CST, UTC-6)
    out = run(make_row())
    assert out.loc[0, "opened_local"].hour == 6
    assert out.loc[0, "opened_hour"] == 6
    assert str(out.loc[0, "opened_utc"].tz) == "UTC"


def test_local_date_can_differ_from_utc_date():
    # 2026-01-01 03:00 UTC is still 2025-12-31 in Chicago
    out = run(make_row(OpenedDateTime=ms("2026-01-01 03:00"), ClosedDateTime=ms("2026-01-02 03:00")))
    assert out.loc[0, "opened_year"] == 2025
    assert out.loc[0, "opened_month"] == 12


def test_report_window_columns_are_dropped():
    out = run(make_row(ReportStartingDate=ms("2025-11-07 00:00"), ReportEndingDate=ms("2026-11-06 00:00")))
    assert "ReportStartingDate" not in out.columns
    assert "ReportEndingDate" not in out.columns


@pytest.mark.parametrize("source", ["Voice in", "voice_in", "VOICE IN"])
def test_normalize_source_variants(source):
    result = clean_311.normalize_source(pd.Series([source]))
    assert result.iloc[0] == "voice_in"
