-- BR8 Q20: BBB 2013J week 5 forumng clicks for Pass/Distinction enrollments.
-- Enrollment is the cohort, so students with no forum clicks remain as zero.
WITH cohort AS (
    SELECT id_student
    FROM fact_enrollment
    WHERE code_module = 'BBB'
      AND code_presentation = '2013J'
      AND final_result IN ('Pass', 'Distinction')
), clicks_by_student AS (
    SELECT
        vle.id_student,
        SUM(vle.sum_click) AS forum_clicks
    FROM fact_vle_daily AS vle
    INNER JOIN dim_vle_site AS site
        ON site.id_site = vle.id_site
       AND site.code_module = vle.code_module
       AND site.code_presentation = vle.code_presentation
    WHERE vle.code_module = 'BBB'
      AND vle.code_presentation = '2013J'
      AND vle.week_no = 5
      AND NOT vle.is_pre_start
      AND site.activity_type = 'forumng'
    GROUP BY vle.id_student
), student_clicks AS (
    SELECT cohort.id_student, COALESCE(clicks.forum_clicks, 0) AS forum_clicks
    FROM cohort
    LEFT JOIN clicks_by_student AS clicks USING (id_student)
), quantiles AS (
    SELECT DISTINCT
        PERCENTILE_CONT(forum_clicks, 0.25) OVER () AS q25_forum_clicks,
        PERCENTILE_CONT(forum_clicks, 0.5) OVER () AS median_forum_clicks,
        PERCENTILE_CONT(forum_clicks, 0.75) OVER () AS q75_forum_clicks
    FROM student_clicks
)
SELECT
    (SELECT COUNT(*) FROM student_clicks) AS n_students,
    quantiles.q25_forum_clicks,
    quantiles.median_forum_clicks,
    quantiles.q75_forum_clicks
FROM quantiles;
