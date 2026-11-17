"""
Add longitude/latitude to the curated 311 data.

Run from the civicpulse folder (after clean_311.py):
    python transformations/pandas/enrich_311.py

CRS verification (done with pyproj):
  - Layer reports WKID 102740 (Esri) / latest WKID 2278 (EPSG).
  - ESRI:102740 and EPSG:2278 are equivalent: NAD83 / Texas South Central,
    units = US survey foot.
  - Output coordinates are WGS84 (EPSG:4326), longitude/latitude in degrees.
"""
import json
from pathlib import Path

import pandas as pd
from pyproj import CRS, Transformer

IN_PATH = Path("data/processed/311/311_curated.parquet")
OUT_PATH = Path("data/processed/311/311_enriched.parquet")
REPORT_PATH = Path("data/processed/311/311_enriched_report.json")

SOURCE_CRS = "EPSG:2278"
TARGET_CRS = "EPSG:4326"

# Loose box around San Antonio / Bexar County, used only as a sanity check.
LON_RANGE = (-99.0, -98.0)
LAT_RANGE = (29.0, 30.0)


def main():
    # Confirm the layer's Esri WKID and EPSG code describe the same CRS.
    esri, epsg = CRS.from_user_input("ESRI:102740"), CRS.from_epsg(2278)
    assert esri.equals(epsg, ignore_axis_order=True), "CRS definitions differ"
    units = {axis.unit_name for axis in epsg.axis_info}
    assert units == {"US survey foot"}, f"Unexpected units: {units}"

    df = pd.read_parquet(IN_PATH)
    print("Rows:", len(df))

    # Source geometry and XCOORD/YCOORD agree (checked in clean_311.py).
    transformer = Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)
    lon, lat = transformer.transform(
        df["geometry_x"].to_numpy(), df["geometry_y"].to_numpy()
    )
    df["longitude"] = lon
    df["latitude"] = lat

    in_box = (
        df["longitude"].between(*LON_RANGE) & df["latitude"].between(*LAT_RANGE)
    )
    df["coord_in_expected_area"] = in_box

    report = {
        "source_crs": SOURCE_CRS,
        "target_crs": TARGET_CRS,
        "source_units": sorted(units),
        "rows": len(df),
        "longitude_min": float(df["longitude"].min()),
        "longitude_max": float(df["longitude"].max()),
        "latitude_min": float(df["latitude"].min()),
        "latitude_max": float(df["latitude"].max()),
        "outside_expected_area": int((~in_box).sum()),
        "null_coordinates": int(df[["longitude", "latitude"]].isna().any(axis=1).sum()),
    }

    assert report["null_coordinates"] == 0, "Null coordinates after conversion"

    df.to_parquet(OUT_PATH, index=False)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)

    print(json.dumps(report, indent=4))
    print("Written:", OUT_PATH)


if __name__ == "__main__":
    main()
