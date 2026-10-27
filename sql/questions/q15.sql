-- Câu 15 (BR5): Bao nhiêu % lượt Withdrawn rút từ ngày 0 trở về trước?
-- Đáp án chuẩn: 30,4% (3.089 / 10.156)
SELECT SUM(CASE WHEN date_unregistration <= 0 THEN 1 ELSE 0 END) AS n_rut_truoc_khai_giang,
       COUNT(*) AS n_withdrawn,
       ROUND(100.0 * SUM(CASE WHEN date_unregistration <= 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct
FROM fact_enrollment
WHERE is_withdrawn
