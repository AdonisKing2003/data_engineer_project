-- Overview page: outcome and engagement summary per offering, plus one
-- school-wide row (code_module and code_presentation NULL) whose n_students
-- counts distinct students across all offerings.
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS n_enrollments,
    COUNT(DISTINCT id_student) AS n_students,
    SUM(CASE WHEN final_result IN ('Pass', 'Distinction') THEN 1 ELSE 0 END) AS n_passed,
    SUM(CASE WHEN final_result = 'Fail' THEN 1 ELSE 0 END) AS n_failed,
    SUM(CASE WHEN final_result = 'Withdrawn' THEN 1 ELSE 0 END) AS n_withdrawn,
    SUM(CASE WHEN no_vle_activity THEN 1 ELSE 0 END) AS n_no_vle_activity,
    SUM(total_clicks) AS total_clicks
FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')
GROUP BY code_module, code_presentation
UNION ALL
SELECT
    NULL,
    NULL,
    COUNT(*),
    COUNT(DISTINCT id_student),
    SUM(CASE WHEN final_result IN ('Pass', 'Distinction') THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_result = 'Fail' THEN 1 ELSE 0 END),
    SUM(CASE WHEN final_result = 'Withdrawn' THEN 1 ELSE 0 END),
    SUM(CASE WHEN no_vle_activity THEN 1 ELSE 0 END),
    SUM(total_clicks)
FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')
ORDER BY code_module, code_presentation;
