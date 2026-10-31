-- Tổng click theo tuần của bản batch, làm đường đối chiếu trên trang "Click thời gian thực" (bản DuckDB).
SELECT
    week_no,
    SUM(clicks_week) AS clicks_batch
FROM read_parquet('data/warehouse/fact_student_week/*.parquet')
GROUP BY week_no
ORDER BY week_no;
