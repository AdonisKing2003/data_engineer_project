-- Câu 18 (TV3 / BR6): 2014J (BBB, DDD, FFF), IMD 90–100% đạt cao hơn 0–10% bao nhiêu điểm %?
-- Đáp án chuẩn: 22,2 điểm (63,3% so với 41,1%)
WITH eligible AS (
    SELECT
        enrollment.id_student,
        enrollment.final_result,
        student.imd_band
    FROM fact_enrollment AS enrollment
    INNER JOIN dim_student AS student
        ON enrollment.id_student = student.id_student
    WHERE enrollment.code_module IN ('BBB', 'DDD', 'FFF')
      AND enrollment.code_presentation = '2014J'
      AND NOT enrollment.withdrawn_before_start
      AND student.imd_band IN ('0-10%', '90-100%')
),
band_rates AS (
    SELECT
        COUNT(DISTINCT CASE WHEN imd_band = '0-10%' THEN id_student END)
            AS n_students_imd_0_10,
        COUNT(CASE WHEN imd_band = '0-10%' THEN 1 END)
            AS n_enrollments_imd_0_10,
        COUNT(CASE WHEN imd_band = '0-10%'
                        AND final_result IN ('Pass', 'Distinction')
                   THEN 1 END)
            AS n_achieved_imd_0_10,
        COUNT(DISTINCT CASE WHEN imd_band = '90-100%' THEN id_student END)
            AS n_students_imd_90_100,
        COUNT(CASE WHEN imd_band = '90-100%' THEN 1 END)
            AS n_enrollments_imd_90_100,
        COUNT(CASE WHEN imd_band = '90-100%'
                        AND final_result IN ('Pass', 'Distinction')
                   THEN 1 END)
            AS n_achieved_imd_90_100
    FROM eligible
),
rates AS (
    SELECT
        *,
        100.0 * n_achieved_imd_0_10 / NULLIF(n_enrollments_imd_0_10, 0)
            AS rate_imd_0_10_unrounded_pct,
        100.0 * n_achieved_imd_90_100 / NULLIF(n_enrollments_imd_90_100, 0)
            AS rate_imd_90_100_unrounded_pct
    FROM band_rates
)
SELECT
    'BBB,DDD,FFF' AS code_module,
    '2014J' AS code_presentation,
    CASE WHEN n_students_imd_0_10 < 30 THEN NULL
         ELSE ROUND(rate_imd_0_10_unrounded_pct, 1) END AS rate_imd_0_10_pct,
    CASE WHEN n_students_imd_90_100 < 30 THEN NULL
         ELSE ROUND(rate_imd_90_100_unrounded_pct, 1) END AS rate_imd_90_100_pct,
    CASE WHEN n_students_imd_0_10 < 30 OR n_students_imd_90_100 < 30 THEN NULL
         ELSE ROUND(ABS(rate_imd_90_100_unrounded_pct - rate_imd_0_10_unrounded_pct), 1)
    END AS gap_pp
FROM rates;
