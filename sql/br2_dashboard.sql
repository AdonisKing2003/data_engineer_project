-- Home contract: selected offering's weekly chart fields and cohort-based click averages.
-- DuckDB reconstructs the mart projection from the local Parquet star tables.
-- Cohort counts include students still enrolled at each week end, even without clicks.
WITH presentations AS (
    SELECT
        code_module,
        code_presentation,
        n_weeks
    FROM read_parquet('data/warehouse/dim_presentation/*.parquet')
    WHERE code_module = ?
      AND code_presentation = ?
), calendar AS (
    SELECT
        presentation.code_module,
        presentation.code_presentation,
        CAST(week_series.week_no AS INTEGER) AS week_no,
        CAST(week_series.week_no AS INTEGER) * 7 + 6 AS week_end_day
    FROM presentations AS presentation
    CROSS JOIN UNNEST(range(0, presentation.n_weeks)) AS week_series(week_no)
), activity_types AS (
    SELECT DISTINCT activity_type
    FROM read_parquet('data/warehouse/dim_vle_site/*.parquet')
    WHERE activity_type IS NOT NULL
), activity_clicks AS (
    SELECT
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        site.activity_type,
        SUM(vle.sum_click) AS activity_type_total_clicks
    FROM read_parquet('data/warehouse/fact_vle_daily/*.parquet') AS vle
    INNER JOIN calendar
        ON calendar.code_module = vle.code_module
       AND calendar.code_presentation = vle.code_presentation
       AND calendar.week_no = vle.week_no
    INNER JOIN read_parquet('data/warehouse/fact_enrollment/*.parquet') AS enrollment
        ON enrollment.id_student = vle.id_student
       AND enrollment.code_module = vle.code_module
       AND enrollment.code_presentation = vle.code_presentation
       AND (
            enrollment.date_unregistration IS NULL
            OR enrollment.date_unregistration > calendar.week_end_day
       )
    INNER JOIN read_parquet('data/warehouse/dim_vle_site/*.parquet') AS site
        ON site.id_site = vle.id_site
       AND site.code_module = vle.code_module
       AND site.code_presentation = vle.code_presentation
    WHERE NOT vle.is_pre_start
    GROUP BY
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        site.activity_type
), enrollment_counts AS (
    SELECT
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        COUNT(enrollment.id_student) AS enrolled_students
    FROM calendar
    LEFT JOIN read_parquet('data/warehouse/fact_enrollment/*.parquet') AS enrollment
        ON enrollment.code_module = calendar.code_module
       AND enrollment.code_presentation = calendar.code_presentation
       AND (
            enrollment.date_unregistration IS NULL
            OR enrollment.date_unregistration > calendar.week_end_day
       )
    GROUP BY
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no
), weekly_clicks AS (
    SELECT
        code_module,
        code_presentation,
        week_no,
        SUM(activity_type_total_clicks) AS offering_week_total_clicks
    FROM activity_clicks
    GROUP BY code_module, code_presentation, week_no
), weekly_metrics AS (
    SELECT
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        enrollment_counts.enrolled_students,
        COALESCE(weekly_clicks.offering_week_total_clicks, 0)
            AS offering_week_total_clicks,
        CAST(COALESCE(weekly_clicks.offering_week_total_clicks, 0) AS DOUBLE)
            / NULLIF(enrollment_counts.enrolled_students, 0)
            AS avg_clicks_per_enrolled_student
    FROM calendar
    INNER JOIN enrollment_counts
        USING (code_module, code_presentation, week_no)
    LEFT JOIN weekly_clicks
        USING (code_module, code_presentation, week_no)
), weekly_activity_grid AS (
    SELECT
        weekly_metrics.code_module,
        weekly_metrics.code_presentation,
        weekly_metrics.week_no,
        weekly_metrics.enrolled_students,
        weekly_metrics.offering_week_total_clicks,
        weekly_metrics.avg_clicks_per_enrolled_student,
        activity_types.activity_type,
        COALESCE(activity_clicks.activity_type_total_clicks, 0)
            AS activity_type_total_clicks
    FROM weekly_metrics
    CROSS JOIN activity_types
    LEFT JOIN activity_clicks
        ON activity_clicks.code_module = weekly_metrics.code_module
       AND activity_clicks.code_presentation = weekly_metrics.code_presentation
       AND activity_clicks.week_no = weekly_metrics.week_no
       AND activity_clicks.activity_type = activity_types.activity_type
)
SELECT
    week_no,
    activity_type,
    CAST(activity_type_total_clicks AS DOUBLE)
        / NULLIF(offering_week_total_clicks, 0) AS activity_type_click_share,
    activity_type_total_clicks,
    enrolled_students,
    avg_clicks_per_enrolled_student,
    CAST(activity_type_total_clicks AS DOUBLE)
        / NULLIF(enrolled_students, 0)
        AS activity_type_avg_clicks_per_enrolled_student
FROM weekly_activity_grid
ORDER BY week_no, activity_type;
