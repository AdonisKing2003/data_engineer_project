-- ==============================================================================
-- BR4: HỆ THỐNG CẢNH BÁO SỚM SINH VIÊN CÓ NGUY CƠ HỌC TẬP THEO TUẦN (AS-OF SNAPSHOT)
-- Phụ trách: Thành viên 2 (TV2)
-- Người dùng: Student Support (Trang Cảnh báo)
-- Bảng chính: fact_student_week (được tính as-of hàng tuần)
-- Bảng nhãn: fact_enrollment (CHỈ DÙNG ĐỂ ĐÁNH GIÁ ĐỘ CHÍNH XÁC, KHÔNG DÙNG ĐỂ TÍNH NGUY CƠ)
-- Tiêu chuẩn: Hợp đồng docs/contract.md & Đặc tả BUSINESS_REQUIREMENTS_SPECIFICATION.md
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. DANH SÁCH SINH VIÊN NGUY CƠ THEO TUẦN (ACTIONABLE INTERVENTION LIST)
-- Áp dụng 4 dấu hiệu rủi ro khách quan (tính đến hết tuần w):
--   - Dấu hiệu 1: clicks_cum < Phân vị 25% (P25) của cả lớp trong cùng đợt học
--   - Dấu hiệu 2: clicks_week = 0 VÀ clicks_prev_week = 0 (2 tuần liên tiếp không tương tác)
--   - Dấu hiệu 3: n_tma_missed_cum > 0 (bỏ lỡ ít nhất 1 bài TMA có trọng số đã hết hạn)
--   - Dấu hiệu 4: avg_score_cum < 40 (điểm trung bình tích lũy các bài đã chấm dưới 40)
-- Sinh viên được đưa vào danh sách cảnh báo khi đạt ít nhất 2 dấu hiệu (risk_score >= 2).
-- ------------------------------------------------------------------------------

WITH cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_week,
        w.clicks_cum,
        w.active_days_week,
        w.sites_week,
        w.n_submitted_cum,
        w.n_late_cum,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        -- Lấy số click của tuần trước đó
        p.clicks_week AS clicks_prev_week
    FROM fact_student_week w
    LEFT JOIN fact_student_week p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4                   -- Tham số tuần: ví dụ tuần 4
      AND w.is_enrolled                   -- Chỉ xét sinh viên còn đang theo học (chưa rút)
      AND w.code_module = 'DDD'           -- Tham số học phần (tùy chọn)
      AND w.code_presentation = '2014J'   -- Tham số đợt học (tùy chọn)
),
cohort_p25 AS (
    -- Tính ngưỡng phân vị 25% click tích lũy theo từng đợt học
    SELECT
        code_module,
        code_presentation,
        QUANTILE_CONT(clicks_cum, 0.25) AS p25_clicks_cum
    FROM cohort
    GROUP BY code_module, code_presentation
),
scored_students AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        c.week_no,
        c.clicks_week,
        c.clicks_prev_week,
        c.clicks_cum,
        p.p25_clicks_cum,
        c.avg_score_cum,
        c.n_tma_missed_cum,
        c.n_late_cum,
        -- 4 Dấu hiệu rủi ro (Risk Flags):
        (c.clicks_cum < p.p25_clicks_cum) AS flag_low_clicks_cum,
        (c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0) AS flag_two_weeks_inactive,
        (c.n_tma_missed_cum > 0) AS flag_missed_tma,
        (c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40) AS flag_low_score,
        -- Điểm nguy cơ từ 0 đến 4:
        (CAST(c.clicks_cum < p.p25_clicks_cum AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40 AS INT64)) AS risk_score
    FROM cohort c
    JOIN cohort_p25 p USING (code_module, code_presentation)
)
SELECT
    id_student,
    code_module,
    code_presentation,
    week_no,
    risk_score,
    CASE 
        WHEN risk_score >= 3 THEN 'High Risk (Đỏ)'
        WHEN risk_score = 2 THEN 'Medium Risk (Vàng)'
        ELSE 'Low Risk (Xanh)'
    END AS risk_level,
    flag_low_clicks_cum,
    flag_two_weeks_inactive,
    flag_missed_tma,
    flag_low_score,
    clicks_cum,
    ROUND(p25_clicks_cum, 1) AS cohort_p25_clicks,
    clicks_week,
    avg_score_cum,
    n_tma_missed_cum
FROM scored_students
WHERE risk_score >= 2
ORDER BY risk_score DESC, clicks_cum ASC;


-- ------------------------------------------------------------------------------
-- 2. ĐÁNH GIÁ HIỆU QUẢ CẢNH BÁO (EFFECTIVENESS EVALUATION: PRECISION & RECALL)
-- Đối chiếu danh sách cảnh báo với nhãn thực tế final_result trong fact_enrollment
-- Tiêu chuẩn:
--   - precision = TP / (TP + FP)  (% sinh viên bị cảnh báo thực sự Fail hoặc Withdrawn)
--   - recall    = TP / (TP + FN)  (% sinh viên Fail/Withdrawn được hệ thống phát hiện)
--   - base_rate = (TP + FN) / All (% sinh viên trượt hoặc bỏ học nền của đợt)
-- Kỳ vọng cho DDD 2014J tuần 4:
--   - Số SV xét: 1.459 | Số SV cảnh báo: 161
--   - Độ chính xác (Precision): 90.1% | Tỷ lệ nền (Base Rate): 45.7%
-- Kỳ vọng cho Toàn bộ các đợt tuần 4 (Câu kiểm 14):
--   - Số SV cảnh báo: 3.958
--   - Độ chính xác (Precision): 80.6% | Độ bao phủ (Recall): 26.9% | Tỷ lệ nền: 43.5%
-- ------------------------------------------------------------------------------

WITH cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.clicks_cum,
        w.clicks_week,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM fact_student_week w
    LEFT JOIN fact_student_week p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4 AND w.is_enrolled
),
p25 AS (
    SELECT
        code_module,
        code_presentation,
        QUANTILE_CONT(clicks_cum, 0.25) AS p25_clicks
    FROM cohort
    GROUP BY code_module, code_presentation
),
scored AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
    FROM cohort c
    JOIN p25 p USING (code_module, code_presentation)
),
labeled AS (
    SELECT
        s.id_student,
        s.code_module,
        s.code_presentation,
        s.is_at_risk,
        (e.final_result IN ('Fail', 'Withdrawn')) AS actual_bad_result
    FROM scored s
    JOIN fact_enrollment e USING (id_student, code_module, code_presentation)
)
SELECT
    COUNT(*) AS total_active_students,
    COUNT(*) FILTER (WHERE is_at_risk) AS n_flagged_students,
    -- Độ chính xác (Precision - %)
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_at_risk AND actual_bad_result) 
          / NULLIF(COUNT(*) FILTER (WHERE is_at_risk), 0), 1) AS precision_pct,
    -- Độ bao phủ (Recall - %)
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_at_risk AND actual_bad_result) 
          / NULLIF(COUNT(*) FILTER (WHERE actual_bad_result), 0), 1) AS recall_pct,
    -- Tỷ lệ nền (Base Rate - %)
    ROUND(100.0 * COUNT(*) FILTER (WHERE actual_bad_result) / COUNT(*), 1) AS base_rate_pct
FROM labeled;
