-- BR7: Tiến trình học tập theo tuần của một sinh viên cụ thể
SELECT
    w.week_no,
    w.clicks_cum,
    w.clicks_week,
    w.avg_score_cum,
    w.n_tma_missed_cum,
    w.is_enrolled,
    e.final_result
FROM fact_student_week w
JOIN fact_enrollment e 
  ON e.id_student = w.id_student
 AND e.code_module = w.code_module
 AND e.code_presentation = w.code_presentation
WHERE w.id_student = ?
  AND w.code_module = ?
  AND w.code_presentation = ?
ORDER BY w.week_no;
