-- Phần mô hình hóa: cùng câu hỏi với pg_week4_flat.sql nhưng trên tài liệu JSONB.
-- Phải mở mọi tài liệu và trải mảng weeks ra mới tìm được tuần 4: mô hình tài liệu hợp với
-- "lấy trọn hồ sơ một sinh viên", không hợp với câu hỏi cắt ngang nhiều tài liệu.
SELECT t.code_module,
       t.code_presentation,
       COUNT(*) AS n_enrolled,
       SUM(CASE WHEN (w ->> 'clicks_week')::bigint = 0 THEN 1 ELSE 0 END) AS n_inactive,
       ROUND(AVG((w ->> 'clicks_cum')::bigint), 2) AS avg_clicks_cum
FROM doc.student_timeline AS t,
     jsonb_array_elements(t.doc -> 'weeks') AS w
WHERE (w ->> 'week_no')::bigint = 4
  AND (w ->> 'is_enrolled')::boolean
GROUP BY t.code_module, t.code_presentation
ORDER BY t.code_module, t.code_presentation
