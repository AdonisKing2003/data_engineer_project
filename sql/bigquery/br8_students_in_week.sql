-- BR8: sinh viên còn học của một đợt tại một tuần (để chọn sinh viên trên trang BR8).
-- week_no là cột phân vùng, lọc bằng tham số nên chỉ đọc một phân vùng.
SELECT id_student
FROM fact_student_week
WHERE code_module = @code_module
  AND code_presentation = @code_presentation
  AND week_no = @week_no
  AND is_enrolled
ORDER BY id_student;
