-- BR7: Phân vị Q25, Median, Q75 về click và điểm theo tuần của một đợt học
SELECT
    week_no,
    COUNT(*) AS n_active_students,
    ROUND(QUANTILE_CONT(clicks_cum, 0.25)) AS q25_clicks,
    ROUND(QUANTILE_CONT(clicks_cum, 0.50)) AS median_clicks,
    ROUND(QUANTILE_CONT(clicks_cum, 0.75)) AS q75_clicks,
    ROUND(QUANTILE_CONT(avg_score_cum, 0.25) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q25_score,
    ROUND(QUANTILE_CONT(avg_score_cum, 0.50) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS median_score,
    ROUND(QUANTILE_CONT(avg_score_cum, 0.75) FILTER (WHERE avg_score_cum IS NOT NULL), 1) AS q75_score
FROM fact_student_week
WHERE code_module = ? AND code_presentation = ?
  AND is_enrolled
GROUP BY week_no
ORDER BY week_no;

