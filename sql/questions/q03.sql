-- Câu 3 (Chung): Đợt nào đông sinh viên nhất?
-- Đáp án chuẩn: CCC 2014J, 2.498 lượt
SELECT code_module, code_presentation, COUNT(*) AS n_luot_dang_ky
FROM fact_enrollment
GROUP BY code_module, code_presentation
ORDER BY n_luot_dang_ky DESC
LIMIT 1
