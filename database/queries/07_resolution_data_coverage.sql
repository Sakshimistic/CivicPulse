-- Data-quality indicator: how many closed requests can be used for resolution metrics.
SELECT count(*) FILTER (WHERE case_status = 'CLOSED')                         AS closed_requests,
       count(*) FILTER (WHERE is_valid_resolution)                            AS valid_resolution,
       count(*) FILTER (WHERE invalid_close_date)                             AS invalid_close_date,
       count(*) FILTER (WHERE negative_duration)                              AS negative_duration,
       round(100.0 * count(*) FILTER (WHERE is_valid_resolution)
             / count(*) FILTER (WHERE case_status = 'CLOSED'), 2)             AS coverage_pct
FROM civicpulse.fact_service_request
WHERE in_report_window;
