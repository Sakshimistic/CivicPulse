-- KPI: top 15 request types by volume with open share and median resolution.
SELECT it.category, it.type_name, count(*) AS requests,
       round(100.0 * count(*) FILTER (WHERE f.case_status = 'OPEN') / count(*), 1) AS open_pct,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.resolution_hours))::numeric, 1) AS median_resolution_hours
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_issue_type it ON it.issue_type_key = f.issue_type_key
WHERE f.in_report_window
GROUP BY it.category, it.type_name
ORDER BY requests DESC
LIMIT 15;
