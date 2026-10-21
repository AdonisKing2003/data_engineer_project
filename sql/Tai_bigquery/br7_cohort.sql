-- ==============================================================================
-- BR7 (BIGQUERY VERSION): THEO DÕI TIẾN ĐỘ CÁ NHÂN SO VỚI PHÂN VỊ LỚP
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TRUY VẤN TỔNG QUÁT: TÍNH DẢI PHÂN VỊ CỦA CẢ LỚP THEO TỪNG TUẦN
-- Cung cấp đường trung vị (Q50) và vùng dải phân vị (Q25 - Q75) cho biểu đồ xu hướng
-- ------------------------------------------------------------------------------
SELECT
    week_no,
    COUNT(*) AS n_active_students,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS q25_clicks_cum,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)] AS median_clicks_cum,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)] AS q75_clicks_cum,
    APPROX_QUANTILES(IF(avg_score_cum IS NOT NULL, avg_score_cum, NULL), 100)[OFFSET(25)] AS q25_score_cum,
    APPROX_QUANTILES(IF(avg_score_cum IS NOT NULL, avg_score_cum, NULL), 100)[OFFSET(50)] AS median_score_cum,
    APPROX_QUANTILES(IF(avg_score_cum IS NOT NULL, avg_score_cum, NULL), 100)[OFFSET(75)] AS q75_score_cum
FROM `dataengineergroup32.oulad.fact_student_week`
WHERE code_module = 'AAA' 
  AND code_presentation = '2014J'
  AND is_enrolled
GROUP BY week_no
ORDER BY week_no;


-- ------------------------------------------------------------------------------
-- 2. TRUY VẤN CHI TIẾT: VỊ THẾ CỦA 1 SINH VIÊN SO VỚI LỚP TẠI TUẦN CHỌN
-- Tính thứ hạng phân vị phần trăm (Percentile Rank 0 - 100%) của sinh viên
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
    FROM `dataengineergroup32.oulad.fact_student_week`
    WHERE code_module = 'AAA' 
      AND code_presentation = '2014J'
      AND week_no = 10
      AND is_enrolled
),
cohort_summary AS (
    SELECT
        COUNT(*) AS total_students,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS q25_clicks,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)] AS q50_clicks,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)] AS q75_clicks,
        APPROX_QUANTILES(avg_score_cum, 100)[OFFSET(50)] AS q50_score
    FROM `dataengineergroup32.oulad.fact_student_week`
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
WHERE c.id_student = 32885;


-- ------------------------------------------------------------------------------
-- 3. BỘ CÂU HỎI NGHIỆP VỤ MẪU (ĐÁNH GIÁ EFFECTIVENESS TỪ 8BR_INFO.MD)
-- ------------------------------------------------------------------------------

-- [Câu 19 - BR7]: AAA 2014J, tuần 10: trung vị tổng click từ đầu đợt của SV còn học?
-- Đáp án chuẩn: 593 click (336 SV, Q25 = 269, Q75 = 1.083)
SELECT
    COUNT(*) AS n_active_students,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS q25_clicks,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)] AS median_clicks,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)] AS q75_clicks
FROM `dataengineergroup32.oulad.fact_student_week`
WHERE code_module = 'AAA' 
  AND code_presentation = '2014J' 
  AND week_no = 10 
  AND is_enrolled;
