-- KPI: open backlog and age by department.
SELECT department_name,
       count(*) AS open_requests,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY open_age_hours) / 24)::numeric, 1) AS median_age_days,
       round((max(open_age_hours) / 24)::numeric, 0) AS oldest_days
FROM civicpulse.v_open_backlog
GROUP BY department_name
ORDER BY open_requests DESC;
