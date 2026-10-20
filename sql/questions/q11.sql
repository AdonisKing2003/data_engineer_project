-- Câu 11 (BR2): FFF 2014J tuần 0 có trung bình bao nhiêu click mỗi SV còn học?
-- Đáp án chuẩn: 2.140 SV, 255.054 click, 119,2 click/SV
SELECT
    code_module,
    code_presentation,
    week_no,
    COUNT(CASE WHEN is_enrolled THEN 1 END) AS enrolled_students,
    SUM(CASE WHEN is_enrolled THEN clicks_week ELSE 0 END) AS total_clicks,
    1.0 * SUM(CASE WHEN is_enrolled THEN clicks_week ELSE 0 END)
        / NULLIF(COUNT(CASE WHEN is_enrolled THEN 1 END), 0)
        AS avg_clicks_per_enrolled_student
FROM fact_student_week
WHERE code_module = 'FFF'
  AND code_presentation = '2014J'
  AND week_no = 0
GROUP BY code_module, code_presentation, week_no;
