-- BR2: weekly VLE clicks per enrolled student and share by activity type.
-- BigQuery version of sql/br2_vle_weekly.sql; preserve its output columns and scope.
-- Enrollment is evaluated at the end of each course week (day 7 * week_no + 6).
-- The denominator includes enrolled students with no VLE clicks that week.
-- fact_vle_daily is already deduplicated at the student/site/day grain.
-- All 20 activity types are emitted for every presentation week; absent activity
-- is represented by zero clicks. A share is NULL when the week has no clicks.
WITH presentations AS (
    SELECT
        code_module,
        code_presentation,
        n_weeks
    FROM dim_presentation
),
calendar AS (
    SELECT
        presentation.code_module,
        presentation.code_presentation,
        CAST(week_series AS INT64) AS week_no,
        CAST(week_series AS INT64) * 7 AS week_start_day,
        CAST(week_series AS INT64) * 7 + 6 AS week_end_day
    FROM presentations AS presentation
    CROSS JOIN UNNEST(GENERATE_ARRAY(0, presentation.n_weeks - 1)) AS week_series
),
enrollment_counts AS (
    SELECT
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        COUNT(enrollment.id_student) AS enrolled_students
    FROM calendar
    LEFT JOIN fact_enrollment AS enrollment
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
),
activity_types AS (
    SELECT DISTINCT activity_type
    FROM dim_vle_site
    WHERE activity_type IS NOT NULL
),
activity_clicks AS (
    SELECT
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        site.activity_type,
        SUM(vle.sum_click) AS activity_type_total_clicks
    FROM fact_vle_daily AS vle
    INNER JOIN calendar
        ON calendar.code_module = vle.code_module
       AND calendar.code_presentation = vle.code_presentation
       AND calendar.week_no = vle.week_no
    INNER JOIN fact_enrollment AS enrollment
        ON enrollment.id_student = vle.id_student
       AND enrollment.code_module = vle.code_module
       AND enrollment.code_presentation = vle.code_presentation
       AND (
            enrollment.date_unregistration IS NULL
            OR enrollment.date_unregistration > calendar.week_end_day
       )
    INNER JOIN dim_vle_site AS site
        ON site.id_site = vle.id_site
       AND site.code_module = vle.code_module
       AND site.code_presentation = vle.code_presentation
    WHERE NOT vle.is_pre_start
    GROUP BY
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        site.activity_type
),
weekly_clicks AS (
    SELECT
        code_module,
        code_presentation,
        week_no,
        SUM(activity_type_total_clicks) AS offering_week_total_clicks
    FROM activity_clicks
    GROUP BY code_module, code_presentation, week_no
),
weekly_metrics AS (
    SELECT
        calendar.code_module,
        calendar.code_presentation,
        calendar.week_no,
        calendar.week_start_day,
        calendar.week_end_day,
        enrollment_counts.enrolled_students,
        COALESCE(weekly_clicks.offering_week_total_clicks, 0) AS offering_week_total_clicks,
        CAST(COALESCE(weekly_clicks.offering_week_total_clicks, 0) AS FLOAT64)
            / NULLIF(enrollment_counts.enrolled_students, 0)
            AS avg_clicks_per_enrolled_student
    FROM calendar
    INNER JOIN enrollment_counts
        USING (code_module, code_presentation, week_no)
    LEFT JOIN weekly_clicks
        USING (code_module, code_presentation, week_no)
),
ranked_weeks AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY code_module, code_presentation
            ORDER BY avg_clicks_per_enrolled_student IS NULL,
                     avg_clicks_per_enrolled_student DESC
        ) AS avg_clicks_rank,
        RANK() OVER (
            PARTITION BY code_module, code_presentation
            ORDER BY offering_week_total_clicks DESC
        ) AS total_clicks_rank
    FROM weekly_metrics
),
weekly_activity_grid AS (
    SELECT
        ranked_weeks.*,
        activity_types.activity_type,
        COALESCE(activity_clicks.activity_type_total_clicks, 0)
            AS activity_type_total_clicks
    FROM ranked_weeks
    CROSS JOIN activity_types
    LEFT JOIN activity_clicks
        ON activity_clicks.code_module = ranked_weeks.code_module
       AND activity_clicks.code_presentation = ranked_weeks.code_presentation
       AND activity_clicks.week_no = ranked_weeks.week_no
       AND activity_clicks.activity_type = activity_types.activity_type
)
SELECT
    code_module,
    code_presentation,
    week_no,
    week_start_day,
    week_end_day,
    activity_type,
    enrolled_students,
    offering_week_total_clicks,
    avg_clicks_per_enrolled_student,
    activity_type_total_clicks,
    CAST(activity_type_total_clicks AS FLOAT64)
        / NULLIF(enrolled_students, 0)
        AS activity_type_avg_clicks_per_enrolled_student,
    CAST(activity_type_total_clicks AS FLOAT64)
        / NULLIF(offering_week_total_clicks, 0)
        AS activity_type_click_share,
    avg_clicks_rank,
    total_clicks_rank
FROM weekly_activity_grid
ORDER BY code_module, code_presentation, week_no, activity_type;
