
import requests
import json
from pathlib import Path
from datetime import datetime, timezone

# 1. API endpoints
BASE_URL = (
    "https://services.arcgis.com/g1fRTDLeMgspWrYp/"
    "ArcGIS/rest/services/311_All_Service_Calls/FeatureServer/0"
)

METADATA_URL = BASE_URL
QUERY_URL = f"{BASE_URL}/query"

# 2. Create a folder to store raw data
RAW_DIR = Path("data/raw/311")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 3. Get dataset metadata
print("Connecting to San Antonio 311 API...")

metadata_response = requests.get(
    METADATA_URL,
    params={"f": "json"},
    timeout=30
)

metadata_response.raise_for_status()
metadata = metadata_response.json()

if "error" in metadata:
    raise RuntimeError(metadata["error"])

print("\nDataset:", metadata.get("name"))
print("Maximum records per request:", metadata.get("maxRecordCount"))

# Print available fields
print("\nAvailable fields:")
for field in metadata.get("fields", []):
    print(field["name"], "-", field["type"])

# 4. Retrieve the first batch of records
params = {
    "where": "1=1",
    "outFields": "*",
    "returnGeometry": "true",
    "resultOffset": 0,
    "resultRecordCount": 2000,
    "f": "json"
}

print("\nFetching first batch of records...")

response = requests.get(
    QUERY_URL,
    params=params,
    timeout=60
)

response.raise_for_status()
data = response.json()

if "error" in data:
    raise RuntimeError(data["error"])

features = data.get("features", [])

print("Records retrieved:", len(features))

# 5. Save original API response
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

output_file = RAW_DIR / f"311_raw_{timestamp}.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2)

print("\nRaw data saved to:", output_file)

# 6. Display a sample record
if features:
    print("\nSample record:")
    print(json.dumps(features[0], indent=2))

print("\nAPI extraction completed!")
