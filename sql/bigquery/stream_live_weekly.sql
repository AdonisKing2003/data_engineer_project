-- Kết quả stream mới nhất theo tuần, cho trang "Click thời gian thực".
-- stream_student_week_latest là view lấy dòng có batch_id lớn nhất của mỗi (SV, đợt, tuần)
-- trong bảng log stream_student_week_updates (stream/stream_kafka.py --to-bq tạo cả hai).
SELECT
    week_no,
    SUM(clicks_week) AS clicks_stream,
    COUNT(*) AS student_weeks,
    MAX(batch_id) AS last_batch,
    MAX(processed_at) AS last_processed_at
FROM stream_student_week_latest
GROUP BY week_no
ORDER BY week_no;
