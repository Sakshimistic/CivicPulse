
import requests
import json

BASE_URL = (
    "https://services.arcgis.com/g1fRTDLeMgspWrYp/"
    "ArcGIS/rest/services/311_All_Service_Calls/FeatureServer/0"
)

QUERY_URL = f"{BASE_URL}/query"

# Helper function to execute API requests
def query_api(params):
    response = requests.get(
        QUERY_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    result = response.json()

    if "error" in result:
        raise RuntimeError(result["error"])

    return result


# 1. Inspect API capabilities
print("\n--- API CAPABILITIES ---")

metadata_response = requests.get(
    BASE_URL,
    params={"f": "json"},
    timeout=30
)

metadata_response.raise_for_status()
metadata = metadata_response.json()

capabilities = metadata.get(
    "advancedQueryCapabilities", {}
)

print("Object ID field:", metadata.get("objectIdField"))
print("Pagination supported:",
      capabilities.get("supportsPagination"))
print("Statistics supported:",
      capabilities.get("supportsStatistics"))
print("Order by supported:",
      capabilities.get("supportsOrderBy"))
print("Geometry type:", metadata.get("geometryType"))
print("Spatial reference:",
      metadata.get("extent", {}).get("spatialReference"))


# 2. Find total number of records
print("\n--- TOTAL RECORD COUNT ---")

count_data = query_api({
    "where": "1=1",
    "returnCountOnly": "true",
    "f": "json"
})

total_records = count_data.get("count")

print("Total records available:", total_records)


# 3. Find the oldest request
print("\n--- OLDEST REQUEST ---")

oldest_data = query_api({
    "where": "OpenedDateTime IS NOT NULL",
    "outFields": "CaseID,OpenedDateTime",
    "returnGeometry": "false",
    "orderByFields": "OpenedDateTime ASC",
    "resultRecordCount": 1,
    "f": "json"
})

print(json.dumps(oldest_data.get("features", []), indent=2))


# 4. Find the newest request
print("\n--- NEWEST REQUEST ---")

newest_data = query_api({
    "where": "OpenedDateTime IS NOT NULL",
    "outFields": "CaseID,OpenedDateTime",
    "returnGeometry": "false",
    "orderByFields": "OpenedDateTime DESC",
    "resultRecordCount": 1,
    "f": "json"
})

print(json.dumps(newest_data.get("features", []), indent=2))


# 5. Count requests by status
print("\n--- REQUESTS BY STATUS ---")

status_data = query_api({
    "where": "1=1",
    "outStatistics": json.dumps([{
        "statisticType": "count",
        "onStatisticField": "OBJECTID",
        "outStatisticFieldName": "request_count"
    }]),
    "groupByFieldsForStatistics": "CaseStatus",
    "orderByFields": "request_count DESC",
    "f": "json"
})

for feature in status_data.get("features", []):
    attributes = feature["attributes"]
    print(
        attributes.get("CaseStatus"),
        ":", attributes.get("request_count")
    )

print("\nData source inspection completed!")
