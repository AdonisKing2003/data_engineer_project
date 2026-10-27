-- Câu 19 (BR7): AAA 2014J, tuần 10: trung vị tổng click từ đầu đợt của SV còn học?
-- Đáp án chuẩn: 593 click (336 SV, Q25 = 269, Q75 = 1.083)
SELECT
    COUNT(*) AS n_active_students,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS q25_clicks,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)] AS median_clicks,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)] AS q75_clicks
FROM fact_student_week
WHERE code_module = 'AAA' 
  AND code_presentation = '2014J' 
  AND week_no = 10 
  AND is_enrolled;
