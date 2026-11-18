# CivicPulse: Smart City Operations Intelligence Platform

An end-to-end data analytics and AI platform that turns public San Antonio 311 service-request data, together with weather, census and geographic data, into insight about municipal service demand, backlogs, resolution performance and geographic patterns.

> **Portfolio disclaimer.** This is a self-directed case study that uses public data. It was not commissioned, adopted or used by the City of San Antonio. It makes no claim of real cost savings or operational improvements. Recommendations are analytical findings or simulated operational recommendations.

## The idea

Cities receive hundreds of thousands of non-emergency service requests: potholes, missed trash pickup, graffiti, stray animals, code violations. The raw records are messy and hard to use for decisions. CivicPulse treats the 311 data as a consulting engagement for a hypothetical city operations team and builds the full chain from raw API data to dashboards and an AI assistant.

### Questions the platform answers

1. What types of service requests are reported, and how is volume changing over time?
2. Which departments and issue types carry the largest workload?
3. How quickly are requests resolved, and how large and old is the open backlog?
4. How do volume and performance vary by council district or area?
5. Where are the recurring hotspots, and when do unusual spikes occur?
6. Do weather, population or neighborhood context help explain the patterns?
7. Can an AI assistant answer operational questions using verified results only?

### Audience

City operations leadership, 311 program managers, department managers, and data and business analysts.

## Data sources

| Source | Role |
|---|---|
| San Antonio 311 All Service Calls (ArcGIS Feature Service) | Primary fact data: every request with category, department, timestamps, status and location |
| NOAA Climate Data Online | Daily weather (precipitation, temperature) for descriptive comparison with weather-related request types |
| US Census American Community Survey | Population and household context for per-capita comparisons |
| San Antonio GIS | Council district and neighborhood boundaries for spatial joins |

## End-to-end workflow

```text
  311 API      NOAA      Census      GIS
     \           |         |         /
      v          v         v        v
 1. INGESTION        raw JSON snapshots + manifests (immutable)
      |
      v
 2. PROFILING        completeness, uniqueness, validity, anomalies
      |
      v
 3. CLEANING         typed, flagged, UTC + local time, lon/lat -> Parquet
      |
      v
 4. WAREHOUSE        PostgreSQL star schema + SQL analytics + dbt tests
      |
      +--------------------+------------------------+
      v                    v                        v
 5. ADVANCED          6. AI ASSISTANT         7. API
    ANALYTICS            grounded in             FastAPI endpoints for
    geospatial,          approved, read-only     metrics and the assistant
    anomalies, PySpark   queries
      |                    |                        |
      +--------------------+------------------------+
                           v
 8. POWER BI DASHBOARDS    Executive, Geographic, Department, Trends + AI

 9. ORCHESTRATION          Prefect schedule, retries, Docker, monitoring
10. TESTING + DOCS         unit/data tests, KPI reconciliation, case study
```

### Stages

1. **Ingestion.** Repeatable API extraction with retries, ID-based batching, record-count reconciliation and a manifest per run. Raw data is never modified.
2. **Profiling and validation.** Quantify missing values, duplicates, date validity and category coverage. Investigate every anomaly before deciding how to treat it.
3. **Cleaning and transformation.** Flag and document bad records instead of silently dropping them. Keep UTC timestamps and derive San Antonio local time. Convert projected coordinates to longitude and latitude. Store curated data as Parquet.
4. **Warehouse and SQL analytics.** A PostgreSQL star schema (service-request fact table plus date, department, issue type and location dimensions). 10 to 15 business queries covering trends, backlog aging, resolution times, district comparisons and weekday/hour patterns. dbt tests for the model.
5. **Advanced analytics.** Seasonality, geographic hotspot analysis, anomaly detection on demand spikes, and a descriptive weather comparison. A PySpark workflow over the full dataset, checked against pandas results.
6. **AI Operations Analyst.** Natural-language questions are mapped to approved metrics or validated read-only SQL. Answers are explained only from the returned results, with definitions, time period and data freshness. When evidence is missing, the assistant says so. Answer accuracy is evaluated against a known question set.
7. **API.** A FastAPI service exposing health, overview, category, department, backlog and geography metrics, plus the assistant endpoint.
8. **Dashboards.** Four Power BI pages: Executive Overview, Geographic Intelligence, Department Performance, and Trends and AI Insights.
9. **Orchestration and deployment.** A scheduled pipeline with retries, notifications, idempotent loads and run tracking, packaged with Docker. A local-first setup, with optional cloud storage and database.
10. **Testing and documentation.** Unit, integration and data-quality tests. KPI reconciliation across Python, SQL and Power BI. Architecture diagram, data dictionary, KPI definitions, limitations and a short demo.

## Key metrics

- Total requests and request volume by category, department and district
- Open backlog and its age
- Median resolution time (valid closed requests only)
- Late rate, based on the source's own late indicator
- Month-over-month and year-over-year change
- Requests per 1,000 residents
- Geographic hotspots

Every KPI is defined, with its formula and caveats, before any SQL or DAX is written.

## Technology

Python (requests, pandas, GeoPandas), PySpark, PostgreSQL, dbt, FastAPI, an LLM API, Power BI, Prefect, Docker, pytest.

## Design principles

- Raw data is immutable, and every run is documented by a manifest.
- Anomalies are flagged and explained, not hidden.
- Time zones are checked against the data, not assumed. True UTC and local time are both kept.
- Weather and demographic comparisons are descriptive and do not claim causation.
- The AI assistant never has unrestricted database access and never invents numbers.
- Public dashboards do not expose exact residential addresses.
- Claims about the data are limited to what the source supports. Source scope, SLA meaning and update cadence are verified before being asserted.

## Planned deliverables

A reproducible pipeline, a documented PostgreSQL warehouse, geospatial and anomaly analysis, a grounded AI assistant with an evaluation, a FastAPI service, a four-page Power BI dashboard, tests, and a full case-study write-up.
