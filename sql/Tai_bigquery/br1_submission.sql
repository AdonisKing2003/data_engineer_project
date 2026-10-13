-- ==============================================================================
-- BR1 (BIGQUERY VERSION): PHÂN BỐ ĐIỂM VÀ TIẾN ĐỘ NỘP BÀI TMA / CMA / EXAM
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

WITH assessment_meta AS (
    SELECT
        a.id_assessment,
        a.code_module,
        a.code_presentation,
        a.assessment_type,
        a.deadline,
        a.weight,
        a.assessment_order,
        a.is_first_weighted_tma
    FROM `dataengineergroup32.oulad.dim_assessment` a
    WHERE a.code_module = 'BBB' AND a.code_presentation = '2014J'
),
enrolled_at_deadline AS (
    SELECT
        a.id_assessment,
        COUNT(DISTINCT e.id_student) AS n_active_students
    FROM assessment_meta a
    JOIN `dataengineergroup32.oulad.fact_enrollment` e
      ON e.code_module = a.code_module
     AND e.code_presentation = a.code_presentation
    WHERE e.date_unregistration IS NULL OR e.date_unregistration > a.deadline
    GROUP BY a.id_assessment
),
submission_stats AS (
    SELECT
        s.id_assessment,
        COUNT(DISTINCT s.id_student) AS n_submitted_total,
        COUNT(DISTINCT IF(NOT s.is_banked, s.id_student, NULL)) AS n_submitted_regular,
        COUNT(DISTINCT IF(s.is_banked, s.id_student, NULL)) AS n_banked,
        COUNT(DISTINCT IF(s.is_late, s.id_student, NULL)) AS n_late,
        COUNT(DISTINCT IF(s.is_pass_score, s.id_student, NULL)) AS n_passed,
        ROUND(AVG(s.score), 2) AS avg_score,
        APPROX_QUANTILES(s.score, 100)[OFFSET(50)] AS median_score,
        APPROX_QUANTILES(s.score, 100)[OFFSET(25)] AS q1_score,
        APPROX_QUANTILES(s.score, 100)[OFFSET(75)] AS q3_score,
        MIN(s.score) AS min_score,
        MAX(s.score) AS max_score
    FROM `dataengineergroup32.oulad.fact_submission` s
    JOIN assessment_meta a ON a.id_assessment = s.id_assessment
    GROUP BY s.id_assessment
)
SELECT
    m.assessment_order,
    m.id_assessment,
    m.assessment_type,
    m.deadline,
    m.weight,
    e.n_active_students,
    s.n_submitted_total,
    s.n_banked,
    s.n_late,
    ROUND(100.0 * s.n_submitted_total / e.n_active_students, 1) AS submission_rate_pct,
    ROUND(100.0 * s.n_late / NULLIF(s.n_submitted_regular, 0), 1) AS late_rate_pct,
    ROUND(100.0 * s.n_passed / NULLIF(s.n_submitted_total - s.n_banked, 0), 1) AS pass_rate_pct,
    s.avg_score,
    s.median_score,
    s.q1_score,
    s.q3_score,
    s.min_score,
    s.max_score
FROM assessment_meta m
LEFT JOIN enrolled_at_deadline e USING (id_assessment)
LEFT JOIN submission_stats s USING (id_assessment)
ORDER BY m.assessment_order;


-- ------------------------------------------------------------------------------
-- BỘ CÂU HỎI NGHIỆP VỤ MẪU (CHO BIGQUERY)
-- ------------------------------------------------------------------------------

-- [Q01 - BR1]: FFF 2013J TMA2 so với TMA1
SELECT
    a.id_assessment,
    a.assessment_order,
    a.assessment_type,
    COUNT(*) AS n_submitted,
    COUNTIF(s.is_late) AS n_late,
    ROUND(100.0 * COUNTIF(s.is_late) / COUNTIF(NOT s.is_banked), 2) AS late_rate_pct
FROM `dataengineergroup32.oulad.dim_assessment` a
JOIN `dataengineergroup32.oulad.fact_submission` s USING (id_assessment)
WHERE a.code_module = 'FFF' 
  AND a.code_presentation = '2013J' 
  AND a.assessment_type = 'TMA'
GROUP BY a.id_assessment, a.assessment_order, a.assessment_type
ORDER BY a.assessment_order
LIMIT 2;


-- [Q02 - BR1]: BBB 2013B vs 2014B CMA1 điểm trung bình
SELECT
    a.code_presentation,
    a.id_assessment,
    a.assessment_order,
    a.assessment_type,
    COUNT(*) AS n_submitted,
    ROUND(AVG(s.score), 2) AS avg_score,
    APPROX_QUANTILES(s.score, 100)[OFFSET(50)] AS median_score
FROM `dataengineergroup32.oulad.dim_assessment` a
JOIN `dataengineergroup32.oulad.fact_submission` s USING (id_assessment)
WHERE a.code_module = 'BBB' 
  AND a.code_presentation IN ('2013B', '2014B') 
  AND a.assessment_type = 'CMA'
  AND a.assessment_order = 1
GROUP BY a.code_presentation, a.id_assessment, a.assessment_order, a.assessment_type
ORDER BY a.code_presentation;


-- [Q03 - BR1]: DDD 2014J TMA3 số sinh viên trượt (< 40)
SELECT
    a.id_assessment,
    a.assessment_order,
    a.assessment_type,
    COUNT(*) AS n_submitted,
    COUNTIF(s.score < 40) AS n_failed_students,
    ROUND(100.0 * COUNTIF(s.score < 40) / COUNT(*), 2) AS fail_rate_pct
FROM `dataengineergroup32.oulad.dim_assessment` a
JOIN `dataengineergroup32.oulad.fact_submission` s USING (id_assessment)
WHERE a.code_module = 'DDD' 
  AND a.code_presentation = '2014J' 
  AND a.assessment_type = 'TMA'
  AND a.assessment_order = 3
GROUP BY a.id_assessment, a.assessment_order, a.assessment_type;

