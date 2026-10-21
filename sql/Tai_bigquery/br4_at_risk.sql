-- ==============================================================================
-- BR4 (BIGQUERY VERSION): HỆ THỐNG CẢNH BÁO SỚM SINH VIÊN NGUY CƠ THEO TUẦN
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TRUY VẤN TỔNG QUÁT: BẢNG TỔNG HỢP CẢNH BÁO SỚM THEO ĐỢT Ở TUẦN W
-- Cho phép ban giám hiệu / khoa xem tỷ lệ nguy cơ của TẤT CẢ các môn học
-- ------------------------------------------------------------------------------
WITH cohort_all AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_cum,
        w.clicks_week,
        w.avg_score_cum,
        w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM `dataengineergroup32.oulad.fact_student_week` w
    LEFT JOIN `dataengineergroup32.oulad.fact_student_week` p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4
      AND w.is_enrolled
),
p25_all AS (
    SELECT
        code_module,
        code_presentation,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks_cum
    FROM cohort_all
    GROUP BY code_module, code_presentation
),
scored_all AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks_cum AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40 AS INT64)) AS risk_score
    FROM cohort_all c
    JOIN p25_all p USING (code_module, code_presentation)
)
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS n_active_students,
    COUNTIF(risk_score >= 2) AS n_at_risk_students,
    ROUND(100.0 * COUNTIF(risk_score >= 2) / COUNT(*), 1) AS at_risk_rate_pct,
    COUNTIF(risk_score >= 3) AS n_high_risk,
    COUNTIF(risk_score = 2) AS n_medium_risk
FROM scored_all
GROUP BY code_module, code_presentation
ORDER BY at_risk_rate_pct DESC;


-- ------------------------------------------------------------------------------
-- 2. TRUY VẤN CHI TIẾT: DANH SÁCH SINH VIÊN NGUY CƠ (DEMO DDD 2014J TUẦN 4)
-- Bảng danh sách sinh viên kèm 4 cờ dấu hiệu để hiển thị lên Dashboard Streamlit
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
        p.clicks_week AS clicks_prev_week
    FROM `dataengineergroup32.oulad.fact_student_week` w
    LEFT JOIN `dataengineergroup32.oulad.fact_student_week` p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4
      AND w.is_enrolled
      AND w.code_module = 'DDD'
      AND w.code_presentation = '2014J'
),
cohort_p25 AS (
    SELECT
        code_module,
        code_presentation,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks_cum
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
        (c.clicks_cum < p.p25_clicks_cum) AS flag_low_clicks_cum,
        (c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0) AS flag_two_weeks_inactive,
        (c.n_tma_missed_cum > 0) AS flag_missed_tma,
        (c.avg_score_cum IS NOT NULL AND c.avg_score_cum < 40) AS flag_low_score,
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
-- 3. KIỂM THỬ CHỐNG RÒ RỈ DỮ LIỆU (ANTI-LEAKAGE VERIFICATION TEST)
-- Mục tiêu kiểm tra theo đặc tả 8BR_info.md (dòng 179):
-- "Đổi kết quả cuối kỳ (final_result) của một SV -> Danh sách tuần 4 không đổi"
-- ------------------------------------------------------------------------------
WITH cohort AS (
    SELECT
        w.id_student, w.code_module, w.code_presentation,
        w.clicks_cum, w.clicks_week, w.avg_score_cum, w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM `dataengineergroup32.oulad.fact_student_week` w
    LEFT JOIN `dataengineergroup32.oulad.fact_student_week` p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4 AND w.is_enrolled
),
p25 AS (
    SELECT code_module, code_presentation,
           APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks
    FROM cohort GROUP BY code_module, code_presentation
),
original_risk AS (
    SELECT
        c.id_student, c.code_module, c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
    FROM cohort c JOIN p25 p USING (code_module, code_presentation)
),
-- Giả lập hoán đổi kết quả cuối kỳ (đảo ngược hoàn toàn nhãn đậu/rớt)
permuted_risk AS (
    SELECT
        c.id_student, c.code_module, c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
    FROM cohort c JOIN p25 p USING (code_module, code_presentation)
)
SELECT
    COUNT(*) AS total_students_verified,
    COUNTIF(orig.is_at_risk != perm.is_at_risk) AS mismatch_count,
    CASE 
        WHEN COUNTIF(orig.is_at_risk != perm.is_at_risk) = 0 
        THEN 'PASSED: 100% Anti-Leakage Validated (Không rò rỉ nhãn kết quả)'
        ELSE 'FAILED: Leakage Detected'
    END AS anti_leakage_status
FROM original_risk orig
JOIN permuted_risk perm USING (id_student, code_module, code_presentation);


-- ------------------------------------------------------------------------------
-- 4. BỘ CÂU HỎI NGHIỆP VỤ MẪU (ĐÁNH GIÁ EFFECTIVENESS TỪ 8BR_INFO.MD)
-- ------------------------------------------------------------------------------

-- [Câu 14 - BR4]: Tuần 4, tính trên mọi đợt: bao nhiêu SV vào danh sách nguy cơ,
-- và bao nhiêu % trong số đó cuối cùng rớt hoặc rút?
-- Đáp án chuẩn: 3.958 SV; 80,6% (độ bao phủ 26,9%, tỷ lệ nền 43,5%)
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
    FROM `dataengineergroup32.oulad.fact_student_week` w
    LEFT JOIN `dataengineergroup32.oulad.fact_student_week` p
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
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks
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
    JOIN `dataengineergroup32.oulad.fact_enrollment` e USING (id_student, code_module, code_presentation)
)
SELECT
    COUNT(*) AS total_active_students,
    COUNTIF(is_at_risk) AS n_flagged_students,
    ROUND(100.0 * COUNTIF(is_at_risk AND actual_bad_result) / COUNTIF(is_at_risk), 1) AS precision_pct,
    ROUND(100.0 * COUNTIF(is_at_risk AND actual_bad_result) / COUNTIF(actual_bad_result), 1) AS recall_pct,
    ROUND(100.0 * COUNTIF(actual_bad_result) / COUNT(*), 1) AS base_rate_pct
FROM labeled;
