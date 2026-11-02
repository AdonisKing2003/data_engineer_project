-- Phần mô hình hóa: dòng thời gian của một sinh viên trong một đợt (trang Sinh viên, BR7), bảng phẳng.
-- SQL chung, chạy được trên BigQuery và PostgreSQL. Sinh viên 11391, AAA 2013J: 43 tuần (-4..38).
SELECT week_no,
       clicks_week,
       clicks_cum,
       n_submitted_cum,
       avg_score_cum,
       is_enrolled
FROM fact_student_week
WHERE id_student = 11391
  AND code_module = 'AAA'
  AND code_presentation = '2013J'
ORDER BY week_no
