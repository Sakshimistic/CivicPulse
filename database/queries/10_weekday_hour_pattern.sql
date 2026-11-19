-- KPI: when requests are opened (local time). Weekday x hour, window cohort.
SELECT d.iso_weekday, d.weekday_name, f.opened_hour, count(*) AS requests
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_date d ON d.date_key = f.opened_date_key
WHERE f.in_report_window
GROUP BY d.iso_weekday, d.weekday_name, f.opened_hour
ORDER BY d.iso_weekday, f.opened_hour;
