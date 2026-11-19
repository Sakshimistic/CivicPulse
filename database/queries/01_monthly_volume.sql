-- KPI: total requests per month and month-over-month change.
-- Complete months only: the window starts 2025-11-07 (Nov 2025 is partial) and the snapshot is 2026-11-13 (Nov 2026 is partial).
WITH monthly AS (
    SELECT d.year_month, count(*) AS requests
    FROM civicpulse.fact_service_request f
    JOIN civicpulse.dim_date d ON d.date_key = f.opened_date_key
    WHERE f.in_report_window AND d.full_date BETWEEN '2025-12-01' AND '2026-10-31'
    GROUP BY d.year_month
)
SELECT year_month, requests,
       round(100.0 * (requests - lag(requests) OVER (ORDER BY year_month))
             / lag(requests) OVER (ORDER BY year_month), 1) AS mom_change_pct
FROM monthly
ORDER BY year_month;
