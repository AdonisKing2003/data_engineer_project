-- BR2 Q9 global clicks by activity_type benchmark variant (bq/wide).
WITH activity_totals AS (
    SELECT activity_type, SUM(sum_click) AS activity_type_total_clicks
    FROM wide_vle_daily
    GROUP BY activity_type
),
totals_with_share AS (
    SELECT
        activity_type,
        activity_type_total_clicks,
        SUM(activity_type_total_clicks) OVER () AS global_total_clicks
    FROM activity_totals
)
SELECT
    activity_type,
    activity_type_total_clicks,
    global_total_clicks,
    ROUND(
        100.0 * activity_type_total_clicks / NULLIF(global_total_clicks, 0),
        1
    ) AS global_activity_type_click_share_pct
FROM totals_with_share
ORDER BY activity_type_total_clicks DESC, activity_type
LIMIT 1;
