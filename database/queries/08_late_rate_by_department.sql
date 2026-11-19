-- KPI: share of closed requests the city marks late (source flag LateYesNo, used as given, meaning unverified).
SELECT dep.department_name,
       count(*) AS closed_requests,
       count(*) FILTER (WHERE f.is_late_source) AS marked_late,
       round(100.0 * count(*) FILTER (WHERE f.is_late_source) / count(*), 1) AS late_pct
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_department dep ON dep.department_key = f.department_key
WHERE f.in_report_window AND f.case_status = 'CLOSED'
GROUP BY dep.department_name
ORDER BY closed_requests DESC;
