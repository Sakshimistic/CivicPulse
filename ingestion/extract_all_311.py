
import requests
import json
import time

from pathlib import Path
from datetime import datetime, timezone


# --------------------------------------------------
# 1. API configuration
# --------------------------------------------------

BASE_URL = (
    "https://services.arcgis.com/g1fRTDLeMgspWrYp/"
    "ArcGIS/rest/services/311_All_Service_Calls/FeatureServer/0"
)

QUERY_URL = f"{BASE_URL}/query"

BATCH_SIZE = 2000

# Create a unique folder for this extraction
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

OUTPUT_DIR = Path("data/raw/311") / f"extraction_{timestamp}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. Create HTTP session
# --------------------------------------------------

session = requests.Session()


def api_request(params, attempts=3):
    """Send an API request with basic retry handling."""

    for attempt in range(1, attempts + 1):

        try:
            response = session.post(
                QUERY_URL,
                data=params,
                timeout=120
            )

            response.raise_for_status()

            result = response.json()

            if "error" in result:
                raise RuntimeError(result["error"])

            return result

        except (requests.RequestException, ValueError, RuntimeError):

            if attempt == attempts:
                raise

            print(f"Request failed. Retry {attempt}/{attempts - 1}")
            time.sleep(2 * attempt)


# --------------------------------------------------
# 3. Retrieve all Object IDs
# --------------------------------------------------

print("Retrieving Object IDs...")

id_response = api_request({
    "where": "1=1",
    "returnIdsOnly": "true",
    "f": "json"
})

object_ids = id_response.get("objectIds", [])

if not object_ids:
    raise RuntimeError("No Object IDs returned by the API.")

object_ids.sort()

total_records = len(object_ids)

print("Total records found:", total_records)


# --------------------------------------------------
# 4. Download records in batches
# --------------------------------------------------

total_downloaded = 0
total_batches = (
    total_records + BATCH_SIZE - 1
) // BATCH_SIZE

print("\nStarting extraction...")
print("Total batches:", total_batches)

for start in range(0, total_records, BATCH_SIZE):

    batch_ids = object_ids[start:start + BATCH_SIZE]

    batch_number = start // BATCH_SIZE + 1

    print(
        f"\nDownloading batch {batch_number}/{total_batches}"
    )

    result = api_request({
        "objectIds": ",".join(map(str, batch_ids)),
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json"
    })

    features = result.get("features", [])

    if len(features) != len(batch_ids):
        raise RuntimeError(
            f"Batch {batch_number}: expected "
            f"{len(batch_ids)} records but received "
            f"{len(features)}. Check this batch before proceeding."
        )

    output_file = (
        OUTPUT_DIR / f"batch_{batch_number:04d}.json"
    )

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(result, file)

    total_downloaded += len(features)

    print(
        f"Saved {len(features)} records | "
        f"Total downloaded: {total_downloaded}"
    )


# --------------------------------------------------
# 5. Save extraction manifest
# --------------------------------------------------

manifest = {
    "dataset": "San Antonio 311 All Service Calls",
    "extraction_timestamp_utc": timestamp,
    "expected_records": total_records,
    "downloaded_records": total_downloaded,
    "batch_size": BATCH_SIZE,
    "total_batches": total_batches,
    "status": (
        "SUCCESS"
        if total_downloaded == total_records
        else "INCOMPLETE"
    )
}

with open(
    OUTPUT_DIR / "manifest.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(manifest, file, indent=4)


print("\n--------------------------------")
print("EXTRACTION COMPLETED")
print("--------------------------------")
print("Expected records:", total_records)
print("Downloaded records:", total_downloaded)
print("Output directory:", OUTPUT_DIR)
print("Manifest:", OUTPUT_DIR / "manifest.json")
