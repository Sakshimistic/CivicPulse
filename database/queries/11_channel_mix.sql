-- KPI: intake channel mix and median resolution by channel.
SELECT sc.channel_label, count(*) AS requests,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS share_pct,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY f.resolution_hours))::numeric, 1) AS median_resolution_hours
FROM civicpulse.fact_service_request f
JOIN civicpulse.dim_source_channel sc ON sc.channel_key = f.channel_key
WHERE f.in_report_window
GROUP BY sc.channel_label
ORDER BY requests DESC;
