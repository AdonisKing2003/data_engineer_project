-- Việc 1.11, ví dụ 2 (BigQuery, gom cụm) và ví dụ 4 (PostgreSQL, chỉ mục).
-- Click theo tuần × loại hoạt động của một đợt: phần nặng nhất của trang Học phần (BR2)
-- khi người dùng chọn một đợt. Viết SQL chung chạy được trên cả BigQuery và PostgreSQL.
-- Đáp án: 366 dòng (tuần × loại hoạt động có click) cho BBB 2014J
SELECT v.week_no,
       s.activity_type,
       SUM(v.sum_click) AS clicks
FROM fact_vle_daily AS v
JOIN dim_vle_site AS s ON s.id_site = v.id_site
WHERE v.code_module = 'BBB'
  AND v.code_presentation = '2014J'
GROUP BY v.week_no, s.activity_type
ORDER BY v.week_no, s.activity_type
