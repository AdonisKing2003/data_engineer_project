-- Phần mô hình hóa: dòng thời gian của một sinh viên, dạng tài liệu JSONB (PostgreSQL).
-- Lấy đúng một tài liệu theo khóa rồi trải mảng weeks ra. Cùng kết quả với timeline_flat.sql.
SELECT (w ->> 'week_no')::bigint AS week_no,
       (w ->> 'clicks_week')::bigint AS clicks_week,
       (w ->> 'clicks_cum')::bigint AS clicks_cum,
       (w ->> 'n_submitted_cum')::bigint AS n_submitted_cum,
       (w ->> 'avg_score_cum')::double precision AS avg_score_cum,
       (w ->> 'is_enrolled')::boolean AS is_enrolled
FROM doc.student_timeline AS t,
     jsonb_array_elements(t.doc -> 'weeks') AS w
WHERE t.id_student = 11391
  AND t.code_module = 'AAA'
  AND t.code_presentation = '2013J'
ORDER BY week_no
