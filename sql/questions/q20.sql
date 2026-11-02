-- Q20 / BR8: Among BBB 2013J students whose final result is Pass/Distinction,
-- what is the median number of forumng clicks in week 5 (including zero-click students)?
-- Expected: n=1,072; Q1=0; median=5; Q3=22.
-- Quartiles use hand-written linear interpolation (same as PERCENTILE_CONT) so the query
-- runs unchanged on BigQuery, PostgreSQL and DuckDB.
WITH cohort AS (
    SELECT id_student
    FROM fact_enrollment
    WHERE code_module = 'BBB'
      AND code_presentation = '2013J'
      AND final_result IN ('Pass', 'Distinction')
), clicks_by_student AS (
    SELECT vle.id_student, SUM(vle.sum_click) AS forum_clicks
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
    LEFT JOIN clicks_by_student AS clicks ON clicks.id_student = cohort.id_student
), ranked AS (
    SELECT forum_clicks,
           ROW_NUMBER() OVER (ORDER BY forum_clicks) AS rn,
           COUNT(*) OVER () AS n
    FROM student_clicks
), positions AS (
    SELECT DISTINCT n,
           1 + 0.25 * (n - 1) AS p25,
           1 + 0.50 * (n - 1) AS p50,
           1 + 0.75 * (n - 1) AS p75
    FROM ranked
)
SELECT
    pos.n AS n_students,
    MAX(CASE WHEN r.rn = FLOOR(pos.p25) THEN r.forum_clicks END)
        + (pos.p25 - FLOOR(pos.p25))
          * (MAX(CASE WHEN r.rn = CEIL(pos.p25) THEN r.forum_clicks END)
             - MAX(CASE WHEN r.rn = FLOOR(pos.p25) THEN r.forum_clicks END)) AS q25_forum_clicks,
    MAX(CASE WHEN r.rn = FLOOR(pos.p50) THEN r.forum_clicks END)
        + (pos.p50 - FLOOR(pos.p50))
          * (MAX(CASE WHEN r.rn = CEIL(pos.p50) THEN r.forum_clicks END)
             - MAX(CASE WHEN r.rn = FLOOR(pos.p50) THEN r.forum_clicks END)) AS median_forum_clicks,
    MAX(CASE WHEN r.rn = FLOOR(pos.p75) THEN r.forum_clicks END)
        + (pos.p75 - FLOOR(pos.p75))
          * (MAX(CASE WHEN r.rn = CEIL(pos.p75) THEN r.forum_clicks END)
             - MAX(CASE WHEN r.rn = FLOOR(pos.p75) THEN r.forum_clicks END)) AS q75_forum_clicks
FROM ranked AS r
CROSS JOIN positions AS pos
GROUP BY pos.n, pos.p25, pos.p50, pos.p75
