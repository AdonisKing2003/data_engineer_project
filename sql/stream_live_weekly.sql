-- Kết quả stream mới nhất theo tuần, cho trang "Click thời gian thực" (bản DuckDB).
-- Đọc các micro-batch Spark ghi ra data/stream/out_kafka/updates/batch_<id>/ và giữ dòng có
-- batch_id lớn nhất của mỗi (SV, đợt, tuần), giống view stream_student_week_latest trên BigQuery.
WITH latest AS (
    SELECT *
    FROM read_parquet('data/stream/out_kafka/updates/*/*.parquet')
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY id_student, code_module, code_presentation, week_no
        ORDER BY batch_id DESC) = 1
)
SELECT
    week_no,
    SUM(clicks_week) AS clicks_stream,
    COUNT(*) AS student_weeks,
    MAX(batch_id) AS last_batch,
    MAX(processed_at) AS last_processed_at
FROM latest
GROUP BY week_no
ORDER BY week_no;
