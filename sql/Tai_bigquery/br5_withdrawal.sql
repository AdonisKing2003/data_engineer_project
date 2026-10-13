-- ==============================================================================
-- BR5 (BIGQUERY VERSION): ĐƯỜNG CONG RÚT LUI THEO TUẦN VÀ TỶ LỆ DUY TRÌ
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

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
