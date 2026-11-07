-- BR4: Cảnh báo sớm sinh viên nguy cơ học tập toàn trường tại tuần week_no (BigQuery)
WITH cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_week,
        w.clicks_cum,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM fact_student_week w
    LEFT JOIN fact_student_week p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = @week_no
      AND w.is_enrolled
),
cohort_p25 AS (
    SELECT DISTINCT
        code_module,
        code_presentation,
        PERCENTILE_CONT(clicks_cum, 0.25) OVER (PARTITION BY code_module, code_presentation) AS p25_clicks_cum
    FROM cohort
),
scored_students AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        c.week_no,
        c.clicks_week,
        c.clicks_cum,
        c.avg_score_cum,
        c.n_tma_missed_cum,
        CAST(c.clicks_cum < p.p25_clicks_cum AS INT64) AS flag_low_clicks,
        CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) AS flag_inactive_2w,
        CAST(c.n_tma_missed_cum > 0 AS INT64) AS flag_missed_tma,
        CAST(c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40 AS INT64) AS flag_low_score
    FROM cohort c
    JOIN cohort_p25 p USING (code_module, code_presentation)
)
SELECT
    s.id_student,
    s.code_module,
    s.code_presentation,
    s.week_no,
    s.clicks_cum,
    s.clicks_week,
    s.avg_score_cum,
    s.n_tma_missed_cum,
    s.flag_low_clicks,
    s.flag_inactive_2w,
    s.flag_missed_tma,
    s.flag_low_score,
    (s.flag_low_clicks + s.flag_inactive_2w + s.flag_missed_tma + s.flag_low_score) AS risk_score,
    e.final_result,
    CAST(e.final_result IN ('Fail', 'Withdrawn') AS INT64) AS is_unsuccessful
FROM scored_students s
JOIN fact_enrollment e USING (id_student, code_module, code_presentation);
