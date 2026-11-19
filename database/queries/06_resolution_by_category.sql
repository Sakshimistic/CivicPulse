-- KPI: median and 90th-percentile resolution hours by category.
-- Mature cohort: opened before 2026-08-01, so slow cases have had time to close (avoids right-censoring bias).
SELECT it.category, count(*) AS closed_valid,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.resolution_hours))::numeric, 1) AS median_hours,
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY f.resolution_hours))::numeric, 1) AS p90_hours,
       round(avg(f.resolution_hours)::numeric, 1) AS mean_hours
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_issue_type it ON it.issue_type_key = f.issue_type_key
JOIN civicpulse.dim_date d ON d.date_key = f.opened_date_key
WHERE f.is_valid_resolution AND f.in_report_window AND d.full_date < '2026-08-01'
GROUP BY it.category
HAVING count(*) >= 100
ORDER BY median_hours;
