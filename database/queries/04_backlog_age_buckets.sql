-- KPI: open backlog by age bucket, as of the snapshot time. All open cases (not only the window cohort).
SELECT CASE WHEN open_age_hours <  24 * 8   THEN '1: 0-7 days'
            WHEN open_age_hours <  24 * 31  THEN '2: 8-30 days'
            WHEN open_age_hours <  24 * 91  THEN '3: 31-90 days'
            WHEN open_age_hours <  24 * 366 THEN '4: 91-365 days'
            ELSE '5: over 365 days' END AS age_bucket,
       count(*) AS open_requests,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct
FROM civicpulse.v_open_backlog
GROUP BY 1
ORDER BY 1;
