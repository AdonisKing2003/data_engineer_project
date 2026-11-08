-- BR8: sinh viên còn học của một đợt tại một tuần (để chọn sinh viên trên trang BR8).
-- Tham số theo thứ tự: code_module, code_presentation, week_no.
SELECT id_student
FROM fact_student_week
WHERE code_module = ?
  AND code_presentation = ?
  AND week_no = ?
  AND is_enrolled
ORDER BY id_student;
