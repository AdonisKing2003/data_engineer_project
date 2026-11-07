-- Tổng click theo tuần của bản batch, làm đường đối chiếu trên trang "Click thời gian thực".
SELECT
    week_no,
    SUM(clicks_week) AS clicks_batch
FROM fact_student_week
GROUP BY week_no
ORDER BY week_no;
