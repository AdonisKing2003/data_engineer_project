-- BR6: achievement-rate gaps between the two extreme IMD bands.
-- Each row pools eligible enrollments from BBB, DDD, and FFF for one presentation.
-- Suppression is based on distinct students; rates use enrollment-grain outcomes.
WITH selected_presentations AS (
    SELECT '2013B' AS code_presentation
    UNION ALL SELECT '2013J'
    UNION ALL SELECT '2014B'
    UNION ALL SELECT '2014J'
),
eligible AS (
    SELECT
        enrollment.id_student,
        enrollment.code_presentation,
        enrollment.final_result,
        student.imd_band
    FROM read_parquet('data/warehouse/fact_enrollment/*.parquet') AS enrollment
    INNER JOIN read_parquet('data/warehouse/dim_student/*.parquet') AS student
        ON enrollment.id_student = student.id_student
    WHERE enrollment.code_module IN ('BBB', 'DDD', 'FFF')
      AND enrollment.code_presentation IN ('2013B', '2013J', '2014B', '2014J')
      AND NOT enrollment.withdrawn_before_start
      AND student.imd_band IN ('0-10%', '90-100%')
),
counts AS (
    SELECT
        code_presentation,
        COUNT(DISTINCT CASE WHEN imd_band = '0-10%' THEN id_student END)
            AS n_students_imd_0_10,
        COUNT(CASE WHEN imd_band = '0-10%' THEN 1 END)
            AS n_enrollments_imd_0_10,
        COUNT(CASE WHEN imd_band = '0-10%'
                        AND final_result IN ('Pass', 'Distinction')
                   THEN 1 END)
            AS n_achieved_imd_0_10,
        COUNT(CASE WHEN imd_band = '0-10%'
                        AND final_result = 'Distinction'
                   THEN 1 END)
            AS n_distinction_imd_0_10,
        COUNT(DISTINCT CASE WHEN imd_band = '90-100%' THEN id_student END)
            AS n_students_imd_90_100,
        COUNT(CASE WHEN imd_band = '90-100%' THEN 1 END)
            AS n_enrollments_imd_90_100,
        COUNT(CASE WHEN imd_band = '90-100%'
                        AND final_result IN ('Pass', 'Distinction')
                   THEN 1 END)
            AS n_achieved_imd_90_100,
        COUNT(CASE WHEN imd_band = '90-100%'
                        AND final_result = 'Distinction'
                   THEN 1 END)
            AS n_distinction_imd_90_100
    FROM eligible
    GROUP BY code_presentation
),
presentation_counts AS (
    SELECT
        selected.code_presentation,
        COALESCE(counts.n_students_imd_0_10, 0) AS n_students_imd_0_10,
        COALESCE(counts.n_enrollments_imd_0_10, 0) AS n_enrollments_imd_0_10,
        COALESCE(counts.n_achieved_imd_0_10, 0) AS n_achieved_imd_0_10,
        COALESCE(counts.n_distinction_imd_0_10, 0) AS n_distinction_imd_0_10,
        COALESCE(counts.n_students_imd_90_100, 0) AS n_students_imd_90_100,
        COALESCE(counts.n_enrollments_imd_90_100, 0) AS n_enrollments_imd_90_100,
        COALESCE(counts.n_achieved_imd_90_100, 0) AS n_achieved_imd_90_100,
        COALESCE(counts.n_distinction_imd_90_100, 0) AS n_distinction_imd_90_100
    FROM selected_presentations AS selected
    LEFT JOIN counts USING (code_presentation)
),
rates AS (
    SELECT
        *,
        CAST(100.0 * n_achieved_imd_0_10
            / NULLIF(n_enrollments_imd_0_10, 0) AS DOUBLE) AS rate_imd_0_10_unrounded_pct,
        CAST(100.0 * n_distinction_imd_0_10
            / NULLIF(n_enrollments_imd_0_10, 0) AS DOUBLE)
            AS rate_distinction_imd_0_10_unrounded_pct,
        CAST(100.0 * n_achieved_imd_90_100
            / NULLIF(n_enrollments_imd_90_100, 0) AS DOUBLE) AS rate_imd_90_100_unrounded_pct,
        CAST(100.0 * n_distinction_imd_90_100
            / NULLIF(n_enrollments_imd_90_100, 0) AS DOUBLE)
            AS rate_distinction_imd_90_100_unrounded_pct
    FROM presentation_counts
)
SELECT
    'BBB,DDD,FFF' AS code_module,
    code_presentation,
    CASE WHEN n_students_imd_0_10 < 30 THEN NULL ELSE n_students_imd_0_10 END
        AS n_students_imd_0_10,
    CASE WHEN n_students_imd_0_10 < 30 THEN NULL ELSE n_enrollments_imd_0_10 END
        AS n_enrollments_imd_0_10,
    CASE WHEN n_students_imd_0_10 < 30 THEN 'n < 30'
         ELSE CAST(n_students_imd_0_10 AS VARCHAR) END AS n_students_imd_0_10_label,
    CASE WHEN n_students_imd_0_10 < 30 THEN NULL
         ELSE ROUND(rate_imd_0_10_unrounded_pct, 1) END AS rate_imd_0_10_pct,
    CASE WHEN n_students_imd_0_10 < 30 THEN NULL
         ELSE ROUND(rate_distinction_imd_0_10_unrounded_pct, 1)
    END AS rate_distinction_imd_0_10_pct,
    CASE WHEN n_students_imd_90_100 < 30 THEN NULL ELSE n_students_imd_90_100 END
        AS n_students_imd_90_100,
    CASE WHEN n_students_imd_90_100 < 30 THEN NULL ELSE n_enrollments_imd_90_100 END
        AS n_enrollments_imd_90_100,
    CASE WHEN n_students_imd_90_100 < 30 THEN 'n < 30'
         ELSE CAST(n_students_imd_90_100 AS VARCHAR) END AS n_students_imd_90_100_label,
    CASE WHEN n_students_imd_90_100 < 30 THEN NULL
         ELSE ROUND(rate_imd_90_100_unrounded_pct, 1) END AS rate_imd_90_100_pct,
    CASE WHEN n_students_imd_90_100 < 30 THEN NULL
         ELSE ROUND(rate_distinction_imd_90_100_unrounded_pct, 1)
    END AS rate_distinction_imd_90_100_pct,
    CASE WHEN n_students_imd_0_10 < 30 OR n_students_imd_90_100 < 30 THEN NULL
         ELSE ROUND(ABS(rate_imd_90_100_unrounded_pct - rate_imd_0_10_unrounded_pct), 1)
    END AS gap_pp,
    CASE WHEN n_students_imd_0_10 < 30 OR n_students_imd_90_100 < 30 THEN NULL
         ELSE ROUND(ABS(rate_distinction_imd_90_100_unrounded_pct
                        - rate_distinction_imd_0_10_unrounded_pct), 1)
    END AS distinction_gap_pp
FROM rates
ORDER BY code_presentation;
