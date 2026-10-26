-- BR8 Q20: forumng clicks in BBB 2013J week 5 for students who passed.
-- Start with enrollment so students with no forum clicks remain in the cohort.
WITH cohort AS (
    SELECT id_student
    FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')
    WHERE code_module = 'BBB'
      AND code_presentation = '2013J'
      AND final_result IN ('Pass', 'Distinction')
), clicks_by_student AS (
    SELECT
        vle.id_student,
        SUM(vle.sum_click) AS forum_clicks
    FROM read_parquet('data/warehouse/fact_vle_daily/*.parquet') AS vle
    INNER JOIN read_parquet('data/warehouse/dim_vle_site/*.parquet') AS site
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
    SELECT
        cohort.id_student,
        COALESCE(clicks.forum_clicks, 0) AS forum_clicks
    FROM cohort
    LEFT JOIN clicks_by_student AS clicks USING (id_student)
)
SELECT
    COUNT(*) AS n_students,
    quantile_cont(forum_clicks, 0.25) AS q25_forum_clicks,
    quantile_cont(forum_clicks, 0.5) AS median_forum_clicks,
    quantile_cont(forum_clicks, 0.75) AS q75_forum_clicks
FROM student_clicks;
