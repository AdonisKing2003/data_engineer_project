-- ==============================================================================
-- BR4 (BIGQUERY VERSION): HỆ THỐNG CẢNH BÁO SỚM SINH VIÊN NGUY CƠ THEO TUẦN
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

WITH cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_week,
        w.clicks_cum,
        w.active_days_week,
        w.sites_week,
        w.n_submitted_cum,
        w.n_late_cum,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM `dataengineergroup32.oulad.fact_student_week` w
    LEFT JOIN `dataengineergroup32.oulad.fact_student_week` p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4
      AND w.is_enrolled
      AND w.code_module = 'DDD'
      AND w.code_presentation = '2014J'
),
cohort_p25 AS (
    SELECT
        code_module,
        code_presentation,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks_cum
    FROM cohort
    GROUP BY code_module, code_presentation
),
scored_students AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        c.week_no,
        c.clicks_week,
        c.clicks_prev_week,
        c.clicks_cum,
        p.p25_clicks_cum,
        c.avg_score_cum,
        c.n_tma_missed_cum,
        c.n_late_cum,
        (c.clicks_cum < p.p25_clicks_cum) AS flag_low_clicks_cum,
        (c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0) AS flag_two_weeks_inactive,
        (c.n_tma_missed_cum > 0) AS flag_missed_tma,
        (c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40) AS flag_low_score,
        (CAST(c.clicks_cum < p.p25_clicks_cum AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40 AS INT64)) AS risk_score
    FROM cohort c
    JOIN cohort_p25 p USING (code_module, code_presentation)
)
SELECT
    id_student,
    code_module,
    code_presentation,
    week_no,
    risk_score,
    CASE 
        WHEN risk_score >= 3 THEN 'High Risk (Đỏ)'
        WHEN risk_score = 2 THEN 'Medium Risk (Vàng)'
        ELSE 'Low Risk (Xanh)'
    END AS risk_level,
    flag_low_clicks_cum,
    flag_two_weeks_inactive,
    flag_missed_tma,
    flag_low_score,
    clicks_cum,
    ROUND(p25_clicks_cum, 1) AS cohort_p25_clicks,
    clicks_week,
    avg_score_cum,
    n_tma_missed_cum
FROM scored_students
WHERE risk_score >= 2
ORDER BY risk_score DESC, clicks_cum ASC;
