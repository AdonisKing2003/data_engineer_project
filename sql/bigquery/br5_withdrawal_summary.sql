-- BR5: Thống kê tỷ lệ rút lui của 22 đợt học tại ngày 0 và ngày 27 (BigQuery)
WITH presentation_base AS (
    SELECT code_module, code_presentation, COUNT(*) AS total_students
    FROM fact_enrollment
    GROUP BY code_module, code_presentation
),
presentation_milestones AS (
    SELECT
        e.code_module,
        e.code_presentation,
        COUNTIF(e.is_withdrawn AND e.date_unregistration <= 0) AS with_day_0,
        COUNTIF(e.is_withdrawn AND e.date_unregistration <= 27) AS with_day_27,
        COUNTIF(e.is_withdrawn) AS with_total
    FROM fact_enrollment e
    GROUP BY e.code_module, e.code_presentation
),
-- Trung vị chính xác (có nội suy) như MEDIAN của DuckDB.
median_unreg AS (
    SELECT DISTINCT
        code_module,
        code_presentation,
        PERCENTILE_CONT(date_unregistration, 0.5) OVER (PARTITION BY code_module, code_presentation) AS median_unreg_day
    FROM fact_enrollment
    WHERE is_withdrawn AND date_unregistration IS NOT NULL
)
SELECT
    m.code_module || ' ' || m.code_presentation AS presentation,
    b.total_students,
    m.with_day_0,
    ROUND(100.0 * m.with_day_0 / b.total_students, 1) AS pct_withdrawn_day_0,
    m.with_day_27,
    ROUND(100.0 * m.with_day_27 / b.total_students, 1) AS pct_withdrawn_day_27,
    m.with_total,
    ROUND(100.0 * m.with_total / b.total_students, 1) AS pct_withdrawn_total,
    u.median_unreg_day
FROM presentation_milestones m
JOIN presentation_base b USING (code_module, code_presentation)
LEFT JOIN median_unreg u USING (code_module, code_presentation)
ORDER BY pct_withdrawn_total DESC;

