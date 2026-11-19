-- KPI: volume by council district. District 0 = Unassigned (not a real district).
-- Raw counts are not need: per-capita rates require Census data (planned).
SELECT cd.district_label, count(*) AS requests,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct,
       count(*) FILTER (WHERE f.case_status = 'OPEN') AS open_requests
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_council_district cd ON cd.district_key = f.district_key
WHERE f.in_report_window
GROUP BY cd.district_key, cd.district_label
ORDER BY cd.district_key;
