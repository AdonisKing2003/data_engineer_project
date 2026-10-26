-- BR6 Q18 pooled 2014J achievement gap with small-cell suppression benchmark variant (pg/wide).
-- Match production suppression: hide all numeric cell counts/rates when distinct n < 30.
WITH eligible AS (
    SELECT
        id_student,
        code_module,
        code_presentation,
        final_result,
        withdrawn_before_start,
        imd_band
    FROM wide_enrollment
    WHERE code_module IN ('BBB', 'DDD', 'FFF')
      AND code_presentation = '2014J'
      AND NOT withdrawn_before_start
      AND imd_band IN ('0-10%', '90-100%')
),
band_rates AS (
    SELECT
        imd_band,
        COUNT(DISTINCT id_student) AS n_students,
        COUNT(*) AS n_enrollments,
        SUM(CASE WHEN final_result IN ('Pass', 'Distinction') THEN 1 ELSE 0 END)
            AS n_achieved
    FROM eligible
    GROUP BY imd_band
),
rates AS (
    SELECT
        imd_band,
        n_students,
        n_enrollments,
        n_achieved,
        CASE WHEN n_students < 30 THEN NULL
             ELSE ROUND(100.0 * n_achieved / NULLIF(n_enrollments, 0), 1)
        END AS achievement_rate_pct
    FROM band_rates
),
pooled AS (
    SELECT
        COALESCE(MAX(CASE WHEN imd_band = '0-10%' THEN n_students END), 0) AS n_students_0_10,
        COALESCE(MAX(CASE WHEN imd_band = '0-10%' THEN n_enrollments END), 0) AS n_enrollments_0_10,
        COALESCE(MAX(CASE WHEN imd_band = '0-10%' THEN n_achieved END), 0) AS n_achieved_0_10,
        MAX(CASE WHEN imd_band = '0-10%' THEN achievement_rate_pct END) AS rate_0_10_pct,
        COALESCE(MAX(CASE WHEN imd_band = '90-100%' THEN n_students END), 0) AS n_students_90_100,
        COALESCE(MAX(CASE WHEN imd_band = '90-100%' THEN n_enrollments END), 0) AS n_enrollments_90_100,
        COALESCE(MAX(CASE WHEN imd_band = '90-100%' THEN n_achieved END), 0) AS n_achieved_90_100,
        MAX(CASE WHEN imd_band = '90-100%' THEN achievement_rate_pct END) AS rate_90_100_pct
    FROM rates
)
SELECT
    CASE WHEN n_students_0_10 < 30 THEN NULL ELSE n_students_0_10 END AS n_students_0_10,
    CASE WHEN n_students_0_10 < 30 THEN NULL ELSE n_enrollments_0_10 END AS n_enrollments_0_10,
    CASE WHEN n_students_0_10 < 30 THEN 'n < 30'
         ELSE CAST(n_students_0_10 AS TEXT) END AS n_students_0_10_label,
    CASE WHEN n_students_0_10 < 30 THEN NULL ELSE rate_0_10_pct END AS rate_0_10_pct,
    CASE WHEN n_students_90_100 < 30 THEN NULL ELSE n_students_90_100 END AS n_students_90_100,
    CASE WHEN n_students_90_100 < 30 THEN NULL ELSE n_enrollments_90_100 END AS n_enrollments_90_100,
    CASE WHEN n_students_90_100 < 30 THEN 'n < 30'
         ELSE CAST(n_students_90_100 AS TEXT) END AS n_students_90_100_label,
    CASE WHEN n_students_90_100 < 30 THEN NULL ELSE rate_90_100_pct END AS rate_90_100_pct,
    CASE WHEN n_students_0_10 < 30 OR n_students_90_100 < 30 THEN NULL
         ELSE ROUND(ABS(rate_90_100_pct - rate_0_10_pct), 1)
    END AS gap_pp
FROM pooled;
