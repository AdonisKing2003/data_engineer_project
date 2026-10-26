-- Câu 9 (BR2): Loại học liệu nào có tổng click cao nhất trên toàn bộ dữ liệu?
-- Đáp án chuẩn: oucontent, 11.206.803 / 39.605.099 click (28,3%)
WITH activity_totals AS (
    SELECT
        site.activity_type,
        SUM(vle.sum_click) AS activity_type_total_clicks
    FROM fact_vle_daily AS vle
    INNER JOIN dim_vle_site AS site
        ON site.id_site = vle.id_site
       AND site.code_module = vle.code_module
       AND site.code_presentation = vle.code_presentation
    GROUP BY site.activity_type
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
