-- BR1: Thống kê tỷ lệ nộp bài, nộp trễ và phân vị điểm cho từng bài kiểm tra của đợt học
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
    FROM dim_assessment a
    WHERE a.code_module = ? AND a.code_presentation = ?
),
enrolled_at_deadline AS (
    SELECT
        a.id_assessment,
        COUNT(DISTINCT e.id_student) AS n_active_students
    FROM assessment_meta a
    JOIN fact_enrollment e
      ON e.code_module = a.code_module
     AND e.code_presentation = a.code_presentation
    WHERE e.date_unregistration IS NULL OR e.date_unregistration > a.deadline
    GROUP BY a.id_assessment
),
submission_stats AS (
    SELECT
        s.id_assessment,
        COUNT(DISTINCT s.id_student) AS n_submitted_total,
        COUNT(DISTINCT s.id_student) FILTER (WHERE NOT s.is_banked) AS n_submitted_regular,
        COUNT(DISTINCT s.id_student) FILTER (WHERE s.is_banked) AS n_banked,
        COUNT(DISTINCT s.id_student) FILTER (WHERE s.is_late) AS n_late,
        ROUND(MEDIAN(s.score) FILTER (WHERE NOT s.score_missing), 1) AS median_score,
        ROUND(QUANTILE_CONT(s.score, 0.25) FILTER (WHERE NOT s.score_missing), 1) AS p25_score,
        ROUND(QUANTILE_CONT(s.score, 0.75) FILTER (WHERE NOT s.score_missing), 1) AS p75_score,
        ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_pass_score) / COUNT(*) FILTER (WHERE NOT s.score_missing), 1) AS pass_rate_pct
    FROM fact_submission s
    JOIN assessment_meta a ON a.id_assessment = s.id_assessment
    GROUP BY s.id_assessment
)
SELECT
    a.id_assessment,
    a.assessment_type || ' ' || CAST(a.id_assessment AS VARCHAR) AS assessment_label,
    a.assessment_type,
    a.assessment_order,
    a.deadline,
    a.weight,
    a.is_first_weighted_tma,
    COALESCE(e.n_active_students, 0) AS active_students,
    COALESCE(s.n_submitted_regular, 0) AS submitted_regular,
    COALESCE(s.n_banked, 0) AS banked_students,
    COALESCE(s.n_late, 0) AS late_submissions,
    CASE 
        WHEN COALESCE(e.n_active_students, 0) = 0 THEN 0.0
        ELSE ROUND(100.0 * COALESCE(s.n_submitted_regular, 0) / e.n_active_students, 1)
    END AS submission_rate_pct,
    CASE 
        WHEN COALESCE(s.n_submitted_regular, 0) = 0 OR a.assessment_type != 'TMA' THEN 0.0
        ELSE ROUND(100.0 * COALESCE(s.n_late, 0) / s.n_submitted_regular, 1)
    END AS late_rate_pct,
    s.p25_score,
    s.median_score,
    s.p75_score,
    s.pass_rate_pct
FROM assessment_meta a
LEFT JOIN enrolled_at_deadline e USING (id_assessment)
LEFT JOIN submission_stats s USING (id_assessment)
ORDER BY a.deadline, a.id_assessment;
