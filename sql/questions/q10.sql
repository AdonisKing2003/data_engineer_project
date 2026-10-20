-- Câu 10 (BR2): Tuần nào có tổng click cao nhất trên toàn bộ các đợt?
-- Đáp án chuẩn: tuần 2, 2.307.080 click
SELECT
    week_no,
    SUM(sum_click) AS total_clicks
FROM fact_vle_daily
GROUP BY week_no
ORDER BY total_clicks DESC, week_no
LIMIT 1;
