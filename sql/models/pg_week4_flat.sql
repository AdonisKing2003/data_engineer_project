-- Phần mô hình hóa: tổng hợp tuần 4 theo đợt trên bảng phẳng (PostgreSQL, schema public).
-- Kiểu câu hỏi của trang Cảnh báo: cắt ngang mọi sinh viên tại một tuần.
SELECT code_module,
       code_presentation,
       COUNT(*) AS n_enrolled,
       SUM(CASE WHEN clicks_week = 0 THEN 1 ELSE 0 END) AS n_inactive,
       ROUND(AVG(clicks_cum), 2) AS avg_clicks_cum
FROM fact_student_week
WHERE week_no = 4
  AND is_enrolled
GROUP BY code_module, code_presentation
ORDER BY code_module, code_presentation
