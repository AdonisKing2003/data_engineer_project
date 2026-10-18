-- Câu 4 (Chung): Bao nhiêu lượt đăng ký không có click VLE nào?
-- Đáp án chuẩn: 3.365 lượt (10,3%)
SELECT SUM(CASE WHEN no_vle_activity THEN 1 ELSE 0 END) AS n_khong_click,
       ROUND(100.0 * SUM(CASE WHEN no_vle_activity THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct
FROM fact_enrollment
