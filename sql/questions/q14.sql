-- Câu 14 (BR4): Tuần 4, tính trên mọi đợt: bao nhiêu SV vào danh sách nguy cơ, và bao nhiêu % trong số đó cuối cùng rớt hoặc rút?
-- Đáp án chuẩn: 3.958 SV; 80,6% (độ bao phủ 26,9%, tỷ lệ nền 43,5%)
WITH cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
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
    WHERE w.week_no = 4 AND w.is_enrolled
),
p25 AS (
    SELECT
        code_module,
        code_presentation,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks
    FROM cohort
    GROUP BY code_module, code_presentation
),
scored AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
    FROM cohort c
    JOIN p25 p USING (code_module, code_presentation)
),
labeled AS (
    SELECT
        s.id_student,
        s.code_module,
        s.code_presentation,
        s.is_at_risk,
        (e.final_result IN ('Fail', 'Withdrawn')) AS actual_bad_result
    FROM scored s
    JOIN fact_enrollment e USING (id_student, code_module, code_presentation)
)
SELECT
    COUNT(*) AS total_active_students,
    COUNTIF(is_at_risk) AS n_flagged_students,
    ROUND(100.0 * COUNTIF(is_at_risk AND actual_bad_result) / COUNTIF(is_at_risk), 1) AS precision_pct,
    ROUND(100.0 * COUNTIF(is_at_risk AND actual_bad_result) / COUNTIF(actual_bad_result), 1) AS recall_pct,
    ROUND(100.0 * COUNTIF(actual_bad_result) / COUNT(*), 1) AS base_rate_pct
FROM labeled;
