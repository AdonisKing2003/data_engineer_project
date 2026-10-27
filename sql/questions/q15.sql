-- Câu 15 (BR5): Bao nhiêu % số lượt Withdrawn rút từ ngày 0 trở về trước?
-- Đáp án chuẩn: 30,4% (3.089 / 10.156)
SELECT
    COUNTIF(is_withdrawn AND date_unregistration <= 0) AS withdrawn_before_or_at_day_0,
    COUNTIF(is_withdrawn) AS total_withdrawn,
    ROUND(100.0 * COUNTIF(is_withdrawn AND date_unregistration <= 0) / COUNTIF(is_withdrawn), 1) AS pct_withdrawn_pre_start
FROM fact_enrollment;
