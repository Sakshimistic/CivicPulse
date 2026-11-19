-- KPI: volume by category with share of total (window cohort).
SELECT it.category, count(*) AS requests,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_issue_type it ON it.issue_type_key = f.issue_type_key
WHERE f.in_report_window
GROUP BY it.category
ORDER BY requests DESC;
