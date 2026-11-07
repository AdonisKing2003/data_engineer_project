-- BR4 school-wide: Bảng tổng hợp tỷ lệ sinh viên nguy cơ theo 22 đợt học ở tuần 4
WITH cohort_all AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_cum,
        w.clicks_week,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM fact_student_week w
    LEFT JOIN fact_student_week p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4
      AND w.is_enrolled
),
p25_all AS (
    SELECT
        code_module,
        code_presentation,
        QUANTILE_CONT(clicks_cum, 0.25) AS p25_clicks_cum
    FROM cohort_all
    GROUP BY code_module, code_presentation
),
scored_all AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks_cum AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40 AS INT64)) AS risk_score
    FROM cohort_all c
    JOIN p25_all p USING (code_module, code_presentation)
)
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS n_active_students,
    COUNT(*) FILTER (WHERE risk_score >= 2) AS n_at_risk_students,
    ROUND(100.0 * COUNT(*) FILTER (WHERE risk_score >= 2) / COUNT(*), 1) AS at_risk_rate_pct,
    COUNT(*) FILTER (WHERE risk_score >= 3) AS n_high_risk,
    COUNT(*) FILTER (WHERE risk_score = 2) AS n_medium_risk
FROM scored_all
GROUP BY code_module, code_presentation
ORDER BY at_risk_rate_pct DESC;

