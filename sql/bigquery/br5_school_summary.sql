-- BR5 toàn trường: câu 15 (% lượt Withdrawn rút từ ngày 0 trở về trước) và câu 16 (ngày rút trung vị).
-- Mẫu số câu 15 gồm cả các lượt Withdrawn không có ngày rút. Trung vị chỉ tính lượt có ngày rút,
-- viết tay (trung bình hai phần tử giữa) để DuckDB và BigQuery cho cùng một kết quả.
WITH withdrawn AS (
    SELECT date_unregistration AS d
    FROM fact_enrollment
    WHERE is_withdrawn
),
ranked AS (
    SELECT d,
           ROW_NUMBER() OVER (ORDER BY d) AS rn,
           COUNT(*) OVER () AS n
    FROM withdrawn
    WHERE d IS NOT NULL
)
SELECT
    (SELECT COUNT(*) FROM withdrawn) AS n_withdrawn,
    (SELECT COUNT(*) FROM withdrawn WHERE d IS NULL) AS n_no_date,
    (SELECT SUM(CASE WHEN d <= 0 THEN 1 ELSE 0 END) FROM withdrawn) AS n_by_day_0,
    (SELECT AVG(d) FROM ranked WHERE rn IN (FLOOR((n + 1) / 2.0), CEIL((n + 1) / 2.0))) AS median_unreg_day
