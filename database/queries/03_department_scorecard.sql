-- KPI: volume, open backlog and median resolution by department (window cohort).
SELECT dep.department_name,
       count(*)                                                            AS requests,
       count(*) FILTER (WHERE f.case_status = 'OPEN')                      AS open_requests,
       round(100.0 * count(*) FILTER (WHERE f.case_status = 'OPEN') / count(*), 1) AS open_pct,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.resolution_hours))::numeric, 1) AS median_resolution_hours
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_department dep ON dep.department_key = f.department_key
WHERE f.in_report_window
GROUP BY dep.department_name
ORDER BY requests DESC;
