-- ==============================================================================
-- BR5 (BIGQUERY VERSION): ĐƯỜNG CONG RÚT LUI THEO TUẦN VÀ TỶ LỆ DUY TRÌ
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TRUY VẤN TỔNG QUÁT: SO SÁNH TỶ LỆ RÚT LUI CỦA TOÀN BỘ 22 ĐỢT
-- Cung cấp bảng dữ liệu để xếp hạng và vẽ biểu đồ so sánh đa đợt (chồng 22 đường)
-- ------------------------------------------------------------------------------
WITH presentation_base AS (
    SELECT
        code_module,
        code_presentation,
        COUNT(*) AS total_students
    FROM `dataengineergroup32.oulad.fact_enrollment`
    GROUP BY code_module, code_presentation
),
presentation_milestones AS (
    SELECT
        e.code_module,
        e.code_presentation,
        -- Rút trước/đúng ngày khai giảng (ngày 0)
        COUNTIF(e.is_withdrawn AND e.date_unregistration <= 0) AS with_day_0,
        -- Rút đến hết tuần 3 (ngày 27)
        COUNTIF(e.is_withdrawn AND e.date_unregistration <= 27) AS with_day_27,
        -- Tổng số rút lui toàn kỳ
        COUNTIF(e.is_withdrawn) AS with_total,
        APPROX_QUANTILES(IF(e.is_withdrawn AND e.date_unregistration IS NOT NULL, e.date_unregistration, NULL), 100)[OFFSET(50)] AS median_unreg_day
    FROM `dataengineergroup32.oulad.fact_enrollment` e
    GROUP BY e.code_module, e.code_presentation
)
SELECT
    m.code_module,
    m.code_presentation,
    b.total_students,
    m.with_day_0,
    ROUND(100.0 * m.with_day_0 / b.total_students, 1) AS pct_withdrawn_day_0,
    m.with_day_27,
    ROUND(100.0 * m.with_day_27 / b.total_students, 1) AS pct_withdrawn_day_27,
    m.with_total,
    ROUND(100.0 * m.with_total / b.total_students, 1) AS pct_withdrawn_total,
    m.median_unreg_day
FROM presentation_milestones m
JOIN presentation_base b USING (code_module, code_presentation)
ORDER BY pct_withdrawn_total DESC;


-- ------------------------------------------------------------------------------
-- 2. TRUY VẤN CHI TIẾT: ĐƯỜNG CONG RÚT LUI THEO TUẦN (DEMO BBB 2014J)
-- Dữ liệu cấp cho biểu đồ bậc thang (Step-line Chart) trên Dashboard
-- ------------------------------------------------------------------------------
WITH presentation_weeks AS (
    SELECT
        p.code_module,
        p.code_presentation,
        w.week_no,
        w.day_to,
        w.is_pre_start
    FROM `dataengineergroup32.oulad.dim_presentation` p
    CROSS JOIN `dataengineergroup32.oulad.dim_week` w
    WHERE p.code_module = 'BBB' 
      AND p.code_presentation = '2014J'
      AND w.week_no >= -4 
      AND w.week_no < p.n_weeks
),
enrollment_base AS (
    SELECT
        COUNT(*) AS total_students
    FROM `dataengineergroup32.oulad.fact_enrollment`
    WHERE code_module = 'BBB' AND code_presentation = '2014J'
),
weekly_dropouts AS (
    SELECT
        pw.week_no,
        pw.day_to,
        COUNTIF(e.date_unregistration IS NOT NULL AND e.date_unregistration <= pw.day_to) AS cum_withdrawn_students,
        COUNTIF(e.date_unregistration IS NOT NULL AND CAST(FLOOR(e.date_unregistration / 7.0) AS INT64) = pw.week_no) AS new_withdrawn_this_week
    FROM presentation_weeks pw
    LEFT JOIN `dataengineergroup32.oulad.fact_enrollment` e
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
    ROUND(100.0 * w.cum_withdrawn_students / b.total_students, 2) AS cum_withdrawal_rate_pct,
    ROUND(100.0 * (b.total_students - w.cum_withdrawn_students) / b.total_students, 2) AS retention_rate_pct
FROM weekly_dropouts w
CROSS JOIN enrollment_base b
ORDER BY w.week_no;


-- ------------------------------------------------------------------------------
-- 3. BỘ CÂU HỎI NGHIỆP VỤ MẪU (ĐÁNH GIÁ EFFECTIVENESS TỪ 8BR_INFO.MD)
-- ------------------------------------------------------------------------------

-- [Câu 15 - BR5]: Bao nhiêu % số lượt Withdrawn rút từ ngày 0 trở về trước?
-- Đáp án chuẩn: 30,4% (3.089 / 10.156)
SELECT
    COUNTIF(is_withdrawn AND date_unregistration <= 0) AS withdrawn_before_or_at_day_0,
    COUNTIF(is_withdrawn) AS total_withdrawn,
    ROUND(100.0 * COUNTIF(is_withdrawn AND date_unregistration <= 0) / COUNTIF(is_withdrawn), 1) AS pct_withdrawn_pre_start
FROM `dataengineergroup32.oulad.fact_enrollment`;


-- [Câu 16 - BR5]: Ngày rút trung vị của sinh viên Withdrawn?
-- Đáp án chuẩn: Ngày 27 (50% ở giữa rơi vào ngày -2 đến ngày 109)
SELECT
    APPROX_QUANTILES(IF(is_withdrawn AND date_unregistration IS NOT NULL, date_unregistration, NULL), 100)[OFFSET(50)] AS median_unreg_day,
    APPROX_QUANTILES(IF(is_withdrawn AND date_unregistration IS NOT NULL, date_unregistration, NULL), 100)[OFFSET(25)] AS q25_unreg_day,
    APPROX_QUANTILES(IF(is_withdrawn AND date_unregistration IS NOT NULL, date_unregistration, NULL), 100)[OFFSET(75)] AS q75_unreg_day
FROM `dataengineergroup32.oulad.fact_enrollment`;


-- [Câu 17 - BR5]: Đợt nào có tỷ lệ Withdrawn cao nhất?
-- Đáp án chuẩn: CCC 2014B, 46,4%
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS total_students,
    COUNTIF(is_withdrawn) AS withdrawn_students,
    ROUND(100.0 * COUNTIF(is_withdrawn) / COUNT(*), 1) AS withdrawal_rate_pct
FROM `dataengineergroup32.oulad.fact_enrollment`
GROUP BY code_module, code_presentation
ORDER BY withdrawal_rate_pct DESC
LIMIT 1;
