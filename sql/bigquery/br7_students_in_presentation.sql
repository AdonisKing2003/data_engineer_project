-- BR7: Danh sách id_student trong một đợt học (BigQuery)
SELECT DISTINCT id_student
FROM fact_enrollment
WHERE code_module = @code_module AND code_presentation = @code_presentation
ORDER BY id_student;
