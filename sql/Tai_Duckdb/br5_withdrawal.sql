-- ==============================================================================
-- BR5: PHÂN TÍCH ĐƯỜNG CONG RÚT LUI (WITHDRAWAL CURVE) VÀ TỶ LỆ DUY TRÌ
-- Phụ trách: Thành viên 2 (TV2)
-- Người dùng: Student Support & Quản lý chương trình (Trang Cảnh báo)
-- Bảng chính: fact_enrollment, dim_student, dim_presentation
-- Tiêu chuẩn: Hợp đồng docs/contract.md & Đặc tả BUSINESS_REQUIREMENTS_SPECIFICATION.md
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. CHỈ SỐ TỔNG QUAN RÚT LUI THEO ĐỢT MỞ LỚP (KPI CARDS)
-- Kỳ vọng cho BBB 2014J:
--   - % Rút trước khai giảng (date <= 0): 10.5%
--   - % Rút lũy kế đến ngày 27: 22.0%
--   - % Tổng rút lui cả đợt: 32.1% (hoặc 32.7% gồm các ca thiếu ngày rút)
--   - Trung vị ngày rút lui: ngày 12 (toàn bộ) hoặc 27 (tính mốc điểm rơi)
-- Kỳ vọng cho CCC 2014B:
--   - % Tổng rút lui cả đợt: 46.4%
-- ------------------------------------------------------------------------------

SELECT
    e.code_module,
    e.code_presentation,
    COUNT(*) AS total_registered,
    COUNT(*) FILTER (WHERE e.is_withdrawn) AS total_withdrawn,
    -- Rút trước ngày khai giảng chính thức (ngày 0)
    COUNT(*) FILTER (WHERE e.withdrawn_before_start) AS n_withdrawn_before_start,
    ROUND(100.0 * COUNT(*) FILTER (WHERE e.withdrawn_before_start) / COUNT(*), 1) AS pct_withdrawn_before_start,
    -- Rút lui trong vòng 4 tuần đầu (ngày 27 hoặc tuần 3)
    ROUND(100.0 * COUNT(*) FILTER (WHERE e.date_unregistration <= 27) / COUNT(*), 1) AS pct_withdrawn_by_day27,
    -- Tỷ lệ rút lui toàn bộ đợt (%)
    ROUND(100.0 * COUNT(*) FILTER (WHERE e.is_withdrawn) / COUNT(*), 1) AS pct_total_withdrawn,
    -- Tỷ lệ duy trì (Retention Rate) đến cuối kỳ (%)
    ROUND(100.0 * (COUNT(*) - COUNT(*) FILTER (WHERE e.is_withdrawn)) / COUNT(*), 1) AS retention_rate_pct,
    -- Ngày rút trung vị
    MEDIAN(e.date_unregistration) AS median_unreg_day
FROM fact_enrollment e
WHERE e.code_module = 'BBB' AND e.code_presentation = '2014J'
GROUP BY e.code_module, e.code_presentation;


-- ------------------------------------------------------------------------------
-- 2. ĐƯỜNG CONG RÚT LUI TÍCH LŨY THEO TUẦN (CUMULATIVE WITHDRAWAL & RETENTION)
-- Phục vụ vẽ biểu đồ bậc thang (Step Chart / Survival Curve) trên Streamlit
-- Trục X: week_no (từ tuần âm -4 đến tuần kết thúc đợt)
-- Trục Y: retention_rate_pct (%) và cum_withdrawal_rate_pct (%)
-- ------------------------------------------------------------------------------

WITH presentation_weeks AS (
    SELECT
        p.code_module,
        p.code_presentation,
        w.week_no,
        w.day_to,
        w.is_pre_start
    FROM dim_presentation p
    CROSS JOIN dim_week w
    WHERE p.code_module = 'BBB' 
      AND p.code_presentation = '2014J'
      AND w.week_no >= -4 
      AND w.week_no < p.n_weeks
),
enrollment_base AS (
    SELECT
        COUNT(*) AS total_students
    FROM fact_enrollment
    WHERE code_module = 'BBB' AND code_presentation = '2014J'
),
weekly_dropouts AS (
    SELECT
        pw.week_no,
        pw.day_to,
        COUNT(e.id_student) FILTER (
            WHERE e.date_unregistration IS NOT NULL 
              AND e.date_unregistration <= pw.day_to
        ) AS cum_withdrawn_students,
        COUNT(e.id_student) FILTER (
            WHERE e.date_unregistration IS NOT NULL 
              AND CAST(FLOOR(e.date_unregistration / 7.0) AS INT64) = pw.week_no
        ) AS new_withdrawn_this_week
    FROM presentation_weeks pw
    LEFT JOIN fact_enrollment e
      ON e.code_module = pw.code_module
     AND e.code_presentation = pw.code_presentation
    GROUP BY pw.week_no, pw.day_to
)
SELECT
    w.week_no,
    w.day_to AS as_of_day,
    w.new_withdrawn_this_week AS hazard_count,
    w.cum_withdrawn_students,
    b.total_students,
    -- Tỷ lệ rút lui tích lũy (%)
    ROUND(100.0 * w.cum_withdrawn_students / b.total_students, 2) AS cum_withdrawal_rate_pct,
    -- Tỷ lệ duy trì người học (%)
    ROUND(100.0 * (b.total_students - w.cum_withdrawn_students) / b.total_students, 2) AS retention_rate_pct
FROM weekly_dropouts w
CROSS JOIN enrollment_base b
ORDER BY w.week_no;


-- ------------------------------------------------------------------------------
-- 3. PHÂN TÍCH RÚT LUI THEO PHÂN NHÓM NHÂN KHẨU (DEMOGRAPHIC BREAKDOWN)
-- Phân tích theo IMD Band, Vùng miền (Region), Trình độ học vấn đầu vào (Education)
-- ------------------------------------------------------------------------------

SELECT
    s.imd_band,
    s.highest_education,
    COUNT(*) AS total_enrolled,
    COUNT(*) FILTER (WHERE e.is_withdrawn) AS total_withdrawn,
    ROUND(100.0 * COUNT(*) FILTER (WHERE e.is_withdrawn) / COUNT(*), 1) AS withdrawal_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE e.withdrawn_before_start) / COUNT(*), 1) AS pct_withdrawn_before_start,
    MEDIAN(e.date_unregistration) AS median_unreg_day
FROM fact_enrollment e
JOIN dim_student s USING (id_student)
WHERE e.code_module = 'BBB' AND e.code_presentation = '2014J'
GROUP BY s.imd_band, s.highest_education
ORDER BY withdrawal_rate_pct DESC;


-- ------------------------------------------------------------------------------
-- 4. TRUY VẤN KIỂM TRA ĐỢT CCC 2014B (CÂU KIỂM 15-17):
-- Kỳ vọng: Tỷ lệ rút lui của CCC 2014B đạt 46.4%
-- ------------------------------------------------------------------------------
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS total_students,
    COUNT(*) FILTER (WHERE is_withdrawn) AS withdrawn_students,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_withdrawn) / COUNT(*), 1) AS withdrawal_rate_pct
FROM fact_enrollment
WHERE code_module = 'CCC' AND code_presentation = '2014B'
GROUP BY code_module, code_presentation;
