-- ==============================================================================
-- BR1 (DUCKDB VERSION): PHÂN BỐ ĐIỂM VÀ TIẾN ĐỘ NỘP BÀI TMA / CMA / EXAM
-- Cú pháp: DuckDB / PostgreSQL
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TRUY VẤN TỔNG QUÁT: TỔNG HỢP TÌNH HÌNH NỘP BÀI VÀ TRỄ HẠN THEO TỪNG ĐỢT HỌC
-- Cung cấp cái nhìn bao quát về tình hình nộp bài trên toàn bộ 22 đợt
-- ------------------------------------------------------------------------------
SELECT
    a.code_module,
    a.code_presentation,
    COUNT(DISTINCT a.id_assessment) AS n_assessments,
    COUNT(*) AS total_submissions,
    COUNT(*) FILTER (WHERE s.is_late) AS total_late_submissions,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*) FILTER (WHERE NOT s.is_banked), 1) AS overall_late_rate_pct,
    ROUND(AVG(s.score), 1) AS avg_score,
    ROUND(MEDIAN(s.score), 1) AS median_score
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.assessment_type IN ('TMA', 'CMA')
GROUP BY a.code_module, a.code_presentation
ORDER BY a.code_module, a.code_presentation;


-- ------------------------------------------------------------------------------
-- 2. TRUY VẤN CHI TIẾT: PHÂN BỐ ĐIỂM VÀ TỶ LỆ NỘP THEO TỪNG BÀI (DEMO BBB 2014J)
-- Dữ liệu cấp cho biểu đồ đường (tỷ lệ nộp/trễ) và biểu đồ hộp (box plot điểm)
-- ------------------------------------------------------------------------------
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
    WHERE a.code_module = 'BBB' AND a.code_presentation = '2014J'
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
        COUNT(DISTINCT s.id_student) FILTER (WHERE s.is_pass_score) AS n_passed,
        ROUND(AVG(s.score), 2) AS avg_score,
        MEDIAN(s.score) AS median_score,
        QUANTILE_CONT(s.score, 0.25) AS q1_score,
        QUANTILE_CONT(s.score, 0.75) AS q3_score,
        MIN(s.score) AS min_score,
        MAX(s.score) AS max_score
    FROM fact_submission s
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
-- 3. BỘ CÂU HỎI NGHIỆP VỤ MẪU (ĐÁNH GIÁ EFFECTIVENESS TỪ 8BR_INFO.MD)
-- ------------------------------------------------------------------------------

-- [Câu 5 - BR1]: Tỷ lệ nộp bài 1752 của AAA 2013J?
-- Đáp án chuẩn: 96,5% (359 / 372), tỷ lệ trễ: 18,4%, điểm trung vị: 72
SELECT
    s.id_assessment,
    COUNT(DISTINCT s.id_student) AS n_submitted,
    e.active_students,
    ROUND(100.0 * COUNT(DISTINCT s.id_student) / e.active_students, 1) AS submission_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*) FILTER (WHERE NOT s.is_banked), 1) AS late_rate_pct,
    MEDIAN(s.score) AS median_score
FROM fact_submission s
CROSS JOIN (
    SELECT COUNT(DISTINCT e.id_student) AS active_students
    FROM fact_enrollment e
    JOIN dim_assessment a ON a.id_assessment = 1752
    WHERE e.code_module = a.code_module 
      AND e.code_presentation = a.code_presentation
      AND (e.date_unregistration IS NULL OR e.date_unregistration > a.deadline)
) e
WHERE s.id_assessment = 1752
GROUP BY s.id_assessment, e.active_students;


-- [Câu 6 - BR1]: TMA nào của BBB 2014J có tỷ lệ nộp trễ cao nhất?
-- Đáp án chuẩn: Bài 15023 (hạn ngày 152), 22,1%
SELECT
    a.id_assessment,
    a.assessment_order,
    a.deadline,
    COUNT(*) AS total_submissions,
    COUNT(*) FILTER (WHERE s.is_late) AS late_submissions,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*) FILTER (WHERE NOT s.is_banked), 1) AS late_rate_pct
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.code_module = 'BBB' 
  AND a.code_presentation = '2014J' 
  AND a.assessment_type = 'TMA'
GROUP BY a.id_assessment, a.assessment_order, a.deadline
ORDER BY late_rate_pct DESC
LIMIT 1;


-- [Câu 7 - BR1]: Tỷ lệ nộp trễ chung của mọi TMA?
-- Đáp án chuẩn: 16,8% (16.320 bài)
SELECT
    COUNT(*) FILTER (WHERE s.is_late) AS n_late_submissions,
    COUNT(*) FILTER (WHERE NOT s.is_banked) AS n_regular_submissions,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*) FILTER (WHERE NOT s.is_banked), 1) AS overall_tma_late_rate_pct
FROM fact_submission s
JOIN dim_assessment a USING (id_assessment)
WHERE a.assessment_type = 'TMA';


-- [Câu 8 - BR1]: Môn nào có điểm TMA trung bình cao nhất và thấp nhất?
-- Đáp án chuẩn: Cao nhất EEE (81,2); thấp nhất GGG (68,5)
SELECT
    a.code_module,
    COUNT(*) AS n_tma_submissions,
    ROUND(AVG(s.score), 1) AS avg_tma_score
FROM fact_submission s
JOIN dim_assessment a USING (id_assessment)
WHERE a.assessment_type = 'TMA' 
  AND NOT s.is_banked
GROUP BY a.code_module
ORDER BY avg_tma_score DESC;
