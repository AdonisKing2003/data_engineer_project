-- BR1 school-wide: Tình hình nộp bài và trễ hạn theo 22 đợt học (BigQuery)
SELECT
    a.code_module,
    a.code_presentation,
    COUNT(DISTINCT a.id_assessment) AS n_assessments,
    COUNT(*) AS total_submissions,
    COUNTIF(s.is_late) AS total_late_submissions,
    ROUND(100.0 * COUNTIF(s.is_late) / NULLIF(COUNTIF(NOT s.is_banked), 0), 1) AS overall_late_rate_pct,
    ROUND(AVG(s.score), 1) AS avg_score,
    APPROX_QUANTILES(s.score, 100)[OFFSET(50)] AS median_score
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.assessment_type IN ('TMA', 'CMA')
GROUP BY a.code_module, a.code_presentation
ORDER BY a.code_module, a.code_presentation;

