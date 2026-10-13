-- ==============================================================================
-- BR7: BẢNG THEO DÕI TIẾN ĐỘ HỌC TẬP CÁ NHÂN SO VỚI PHÂN VỊ CỦA NHÓM CÙNG LỚP
-- Phụ trách: Thành viên 2 (TV2)
-- Người dùng: Sinh viên (Trang Sinh viên)
-- Bảng chính: fact_student_week
-- Tiêu chuẩn: Hợp đồng docs/contract.md & Đặc tả BUSINESS_REQUIREMENTS_SPECIFICATION.md
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TÍNH DẢI PHÂN VỊ CỦA CẢ LỚP THEO TUẦN (BENCHMARK QUANTILES FOR COHORT)
-- Cung cấp đường trung vị (Q50) và vùng dải mờ (Q25 - Q75) cho biểu đồ xu hướng
-- Kỳ vọng cho AAA 2014J tuần 10 (Câu kiểm 19):
--   - Số SV còn học (is_enrolled): 336 sinh viên
--   - Phân vị 25% (Q25): 269 clicks
--   - Phân vị 50% (Q50 - Median): 593 clicks
--   - Phân vị 75% (Q75): 1.083 clicks
-- ------------------------------------------------------------------------------

SELECT
    week_no,
    COUNT(*) AS n_active_students,
    -- Phân vị tương tác click tích lũy của lớp
    ROUND(QUANTILE_CONT(clicks_cum, 0.25)) AS q25_clicks_cum,
    ROUND(QUANTILE_CONT(clicks_cum, 0.50)) AS median_clicks_cum,
    ROUND(QUANTILE_CONT(clicks_cum, 0.75)) AS q75_clicks_cum,
    -- Phân vị điểm trung bình tích lũy của lớp (bỏ qua sinh viên chưa có bài chấm)
    ROUND(QUANTILE_CONT(avg_score_cum, 0.25) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q25_score_cum,
    ROUND(QUANTILE_CONT(avg_score_cum, 0.50) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS median_score_cum,
    ROUND(QUANTILE_CONT(avg_score_cum, 0.75) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q75_score_cum
FROM fact_student_week
WHERE code_module = 'AAA' 
  AND code_presentation = '2014J'
  AND is_enrolled
GROUP BY week_no
ORDER BY week_no;


-- ------------------------------------------------------------------------------
-- 2. VỊ THẾ CÁ NHÂN CỦA 1 SINH VIÊN SO VỚI LỚP TẠI TUẦN CHỌN
-- Tính thứ hạng phân vị phần trăm (Percentile Rank 0 - 100%) của sinh viên
-- Đảm bảo bảo mật: chỉ lấy dữ liệu của chính sinh viên đang đăng nhập + phân vị tổng hợp
-- ------------------------------------------------------------------------------

WITH cohort AS (
    SELECT
        id_student,
        clicks_cum,
        avg_score_cum,
        PERCENT_RANK() OVER (ORDER BY clicks_cum) * 100.0 AS click_percentile_rank,
        PERCENT_RANK() OVER (
            PARTITION BY (avg_score_cum IS NOT NULL) 
            ORDER BY avg_score_cum
        ) * 100.0 AS score_percentile_rank
    FROM fact_student_week
    WHERE code_module = 'AAA' 
      AND code_presentation = '2014J'
      AND week_no = 10
      AND is_enrolled
),
cohort_summary AS (
    SELECT
        COUNT(*) AS total_students,
        ROUND(QUANTILE_CONT(clicks_cum, 0.25)) AS q25_clicks,
        ROUND(QUANTILE_CONT(clicks_cum, 0.50)) AS q50_clicks,
        ROUND(QUANTILE_CONT(clicks_cum, 0.75)) AS q75_clicks,
        ROUND(QUANTILE_CONT(avg_score_cum, 0.50) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q50_score
    FROM fact_student_week
    WHERE code_module = 'AAA' 
      AND code_presentation = '2014J'
      AND week_no = 10
      AND is_enrolled
)
SELECT
    c.id_student,
    c.clicks_cum AS student_clicks_cum,
    ROUND(c.click_percentile_rank, 1) AS click_percentile_pct,
    s.q25_clicks AS cohort_q25_clicks,
    s.q50_clicks AS cohort_median_clicks,
    s.q75_clicks AS cohort_q75_clicks,
    c.avg_score_cum AS student_avg_score,
    ROUND(c.score_percentile_rank, 1) AS score_percentile_pct,
    s.q50_score AS cohort_median_score,
    s.total_students AS total_active_peers
FROM cohort c
CROSS JOIN cohort_summary s
WHERE c.id_student = 32885;  -- Thay bằng id_student của sinh viên đang tra cứu


-- ------------------------------------------------------------------------------
-- 3. TRUY VẤN KIỂM CHỨNG NHANH CÂU HỎI MẪU 19 (AAA 2014J TUẦN 10):
-- Kỳ vọng: n = 336; quantiles 25/50/75 = 269 / 593 / 1083
-- ------------------------------------------------------------------------------
SELECT
    COUNT(*) AS n_active_students,
    ROUND(QUANTILE_CONT(clicks_cum, 0.25)) AS q25,
    ROUND(QUANTILE_CONT(clicks_cum, 0.50)) AS q50,
    ROUND(QUANTILE_CONT(clicks_cum, 0.75)) AS q75
FROM fact_student_week
WHERE code_module = 'AAA' 
  AND code_presentation = '2014J' 
  AND week_no = 10 
  AND is_enrolled;
