-- Câu 1 (Chung): Bộ dữ liệu có bao nhiêu lượt đăng ký và bao nhiêu sinh viên?
-- Đáp án chuẩn: 32.593 lượt; 28.785 SV
SELECT COUNT(*) AS n_luot_dang_ky,
       COUNT(DISTINCT id_student) AS n_sinh_vien
FROM fact_enrollment
