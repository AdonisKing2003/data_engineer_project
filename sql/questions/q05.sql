-- Câu 5 (BR1): Tỷ lệ nộp bài 1752 của AAA 2013J?
-- Đáp án chuẩn: 96,5% (359 / 372), tỷ lệ trễ: 18,4%, điểm trung vị: 72
SELECT
    s.id_assessment,
    COUNT(DISTINCT s.id_student) AS n_submitted,
    e.active_students,
    ROUND(100.0 * COUNT(DISTINCT s.id_student) / e.active_students, 1) AS submission_rate_pct,
    ROUND(100.0 * COUNTIF(s.is_late) / COUNTIF(NOT s.is_banked), 1) AS late_rate_pct,
    APPROX_QUANTILES(s.score, 100)[OFFSET(50)] AS median_score
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
