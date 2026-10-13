-- ==============================================================================
-- BR1: PHÂN BỐ ĐIỂM VÀ TIẾN ĐỘ NỘP BÀI TMA / CMA / EXAM
-- Phụ trách: Thành viên 2 (TV2)
-- Người dùng: Module Chair (Trang Học phần)
-- Bảng chính: fact_submission, dim_assessment, fact_enrollment
-- Tiêu chuẩn: Hợp đồng docs/contract.md & Đặc tả BUSINESS_REQUIREMENTS_SPECIFICATION.md
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TỔNG QUAN TIẾN ĐỘ VÀ KẾT QUẢ TỪNG BÀI ĐÁNH GIÁ (THEO HỌC PHẦN & ĐỢT HỌC)
-- Công thức:
--   - Mẫu số SV còn học tại hạn nộp: date_unregistration IS NULL OR date_unregistration > deadline
--   - SV nộp bài bình thường: NOT is_banked
--   - SV chuyển điểm: is_banked
--   - Nộp trễ (chỉ tính cho TMA): is_late (được xác định sẵn trong fact_submission)
--   - Điểm trung bình / Trung vị: tính trên các bài nộp có điểm (score IS NOT NULL)
--   - Tỷ lệ đạt bài: score >= 40 (cờ is_pass_score)
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
    -- Đếm số sinh viên còn đang theo học tính đến thời điểm hạn nộp bài
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
        ROUND(AVG(s.score) FILTER (WHERE s.score IS NOT NULL), 2) AS avg_score,
        ROUND(MEDIAN(s.score) FILTER (WHERE s.score IS NOT NULL), 1) AS median_score,
        -- Phân vị 25% (Q1) và 75% (Q3) để dựng Box Plot
        QUANTILE_CONT(s.score, 0.25) FILTER (WHERE s.score IS NOT NULL) AS q1_score,
        QUANTILE_CONT(s.score, 0.75) FILTER (WHERE s.score IS NOT NULL) AS q3_score,
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
    -- Tỷ lệ nộp bài (%) = SV nộp bài / SV còn học tại hạn nộp
    ROUND(100.0 * s.n_submitted_total / e.n_active_students, 1) AS submission_rate_pct,
    -- Tỷ lệ nộp trễ (%) = SV nộp trễ / SV nộp bài thực tế (trừ bài banked)
    ROUND(100.0 * s.n_late / NULLIF(s.n_submitted_regular, 0), 1) AS late_rate_pct,
    -- Tỷ lệ đạt (%) = SV điểm >= 40 / Tổng SV có điểm
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
-- 2. TRUY VẤN KIỂM TRA BÀI 1752 (CÂU KIỂM 5-8):
-- Kỳ vọng:
--   - Tỷ lệ nộp bài: 96.5%
--   - Tỷ lệ nộp trễ: 18.4%
--   - Trung vị điểm: 72
-- ------------------------------------------------------------------------------
SELECT
    s.id_assessment,
    COUNT(DISTINCT s.id_student) AS n_submitted,
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


-- ------------------------------------------------------------------------------
-- 3. TỶ LỆ NỘP TRỄ CHUNG CỦA TOÀN BỘ BÀI TMA TRÊN HỆ THỐNG
-- Kỳ vọng: 16.8% (16.320 bài trễ / tổng bài TMA không banked)
-- ------------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_tma_submissions,
    COUNT(*) FILTER (WHERE s.is_late) AS total_late_tma,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*), 1) AS overall_tma_late_pct
FROM fact_submission s
JOIN dim_assessment a USING (id_assessment)
WHERE a.assessment_type = 'TMA' AND NOT s.is_banked;


-- ------------------------------------------------------------------------------
-- 4. BỘ CÂU HỎI NGHIỆP VỤ MẪU (EFFECTIVENESS QUESTIONS TỪ TÀI LIỆU ĐẶC TẢ)
-- ------------------------------------------------------------------------------

-- [Q01 - BR1]: Trong kỳ 2013J của môn FFF, bài kiểm tra TMA2 có tỷ lệ sinh viên nộp trễ hạn
-- cao hơn bao nhiêu phần trăm so với bài TMA1?
-- Đáp án: TMA2 (11.93%) cao hơn TMA1 (8.68%) là 3.25 điểm phần trăm.
SELECT
    a.id_assessment,
    a.assessment_order,
    a.assessment_type,
    COUNT(*) AS n_submitted,
    COUNT(*) FILTER (WHERE s.is_late) AS n_late,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.is_late) / COUNT(*) FILTER (WHERE NOT s.is_banked), 2) AS late_rate_pct
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.code_module = 'FFF' 
  AND a.code_presentation = '2013J' 
  AND a.assessment_type = 'TMA'
GROUP BY a.id_assessment, a.assessment_order, a.assessment_type
ORDER BY a.assessment_order
LIMIT 2;


-- [Q02 - BR1]: Điểm trung bình của bài CMA1 môn BBB có chênh lệch đáng kể giữa hai đợt mở lớp 2013B và 2014B hay không?
-- Đáp án: Không chênh lệch đáng kể (2013B đạt 93.81 điểm vs 2014B đạt 93.83 điểm, chênh lệch 0.02 điểm).
SELECT
    a.code_presentation,
    a.id_assessment,
    a.assessment_order,
    a.assessment_type,
    COUNT(*) AS n_submitted,
    ROUND(AVG(s.score), 2) AS avg_score,
    MEDIAN(s.score) AS median_score
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.code_module = 'BBB' 
  AND a.code_presentation IN ('2013B', '2014B') 
  AND a.assessment_type = 'CMA'
  AND a.assessment_order = 1
GROUP BY a.code_presentation, a.id_assessment, a.assessment_order, a.assessment_type
ORDER BY a.code_presentation;


-- [Q03 - BR1]: Có bao nhiêu sinh viên đạt điểm dưới 40 (trượt) trong bài kiểm tra TMA3 của môn DDD kỳ 2014J?
-- Đáp án: Có đúng 40 sinh viên trượt (trên tổng số 1.231 bài nộp, chiếm tỷ lệ 3.25%).
SELECT
    a.id_assessment,
    a.assessment_order,
    a.assessment_type,
    COUNT(*) AS n_submitted,
    COUNT(*) FILTER (WHERE s.score < 40) AS n_failed_students,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.score < 40) / COUNT(*), 2) AS fail_rate_pct
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.code_module = 'DDD' 
  AND a.code_presentation = '2014J' 
  AND a.assessment_type = 'TMA'
  AND a.assessment_order = 3
GROUP BY a.id_assessment, a.assessment_order, a.assessment_type;

