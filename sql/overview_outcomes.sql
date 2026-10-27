-- Overview page: final-result mix per offering (enrollment grain).
SELECT
    code_module,
    code_presentation,
    final_result,
    COUNT(*) AS n_enrollments
FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')
GROUP BY code_module, code_presentation, final_result
ORDER BY code_module, code_presentation, final_result;
