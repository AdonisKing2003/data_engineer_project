-- Phần mô hình hóa: dòng thời gian của một sinh viên, bảng dạng lồng (BigQuery).
-- Lấy đúng một dòng rồi trải mảng weeks ra thành các tuần. Cùng kết quả với timeline_flat.sql.
SELECT w.week_no,
       w.clicks_week,
       w.clicks_cum,
       w.n_submitted_cum,
       w.avg_score_cum,
       w.is_enrolled
FROM nested_student_timeline AS t, UNNEST(t.weeks) AS w
WHERE t.id_student = 11391
  AND t.code_module = 'AAA'
  AND t.code_presentation = '2013J'
ORDER BY w.week_no
