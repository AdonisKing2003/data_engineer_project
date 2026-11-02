-- BR7: Phân vị Q25, Median, Q75 về click và điểm theo tuần của một đợt học (BigQuery)
SELECT
    week_no,
    COUNT(*) AS n_active_students,
    ROUND(APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)]) AS q25_clicks,
    ROUND(APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)]) AS median_clicks,
    ROUND(APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)]) AS q75_clicks,
    ROUND(APPROX_QUANTILES(IF(avg_score_cum IS NOT NULL, avg_score_cum, NULL), 100)[OFFSET(25)], 1) AS q25_score,
    ROUND(APPROX_QUANTILES(IF(avg_score_cum IS NOT NULL, avg_score_cum, NULL), 100)[OFFSET(50)], 1) AS median_score,
    ROUND(APPROX_QUANTILES(IF(avg_score_cum IS NOT NULL, avg_score_cum, NULL), 100)[OFFSET(75)], 1) AS q75_score
FROM fact_student_week
WHERE code_module = @code_module AND code_presentation = @code_presentation
  AND is_enrolled
GROUP BY week_no
ORDER BY week_no;

