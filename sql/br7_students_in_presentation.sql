-- BR7: Danh sách id_student trong một đợt học
SELECT DISTINCT id_student
FROM fact_enrollment
WHERE code_module = ? AND code_presentation = ?
ORDER BY id_student;
