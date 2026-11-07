-- BR7: Phân vị Q25, Median, Q75 về click và điểm theo tuần của một đợt học (BigQuery)
-- PERCENTILE_CONT cho phân vị chính xác (có nội suy) như QUANTILE_CONT của DuckDB; nó bỏ qua NULL
-- nên phân vị điểm chỉ tính sinh viên đã có điểm.
WITH active AS (
    SELECT week_no, clicks_cum, avg_score_cum
    FROM fact_student_week
    WHERE code_module = @code_module AND code_presentation = @code_presentation
      AND is_enrolled
),
quantiles AS (
    SELECT DISTINCT
        week_no,
        PERCENTILE_CONT(clicks_cum, 0.25) OVER w AS q25_clicks,
        PERCENTILE_CONT(clicks_cum, 0.5) OVER w AS median_clicks,
        PERCENTILE_CONT(clicks_cum, 0.75) OVER w AS q75_clicks,
        PERCENTILE_CONT(avg_score_cum, 0.25) OVER w AS q25_score,
        PERCENTILE_CONT(avg_score_cum, 0.5) OVER w AS median_score,
        PERCENTILE_CONT(avg_score_cum, 0.75) OVER w AS q75_score
    FROM active
    WINDOW w AS (PARTITION BY week_no)
),
counts AS (
    SELECT week_no, COUNT(*) AS n_active_students
    FROM active
    GROUP BY week_no
)
SELECT
    c.week_no,
    c.n_active_students,
    ROUND(q.q25_clicks) AS q25_clicks,
    ROUND(q.median_clicks) AS median_clicks,
    ROUND(q.q75_clicks) AS q75_clicks,
    ROUND(q.q25_score, 1) AS q25_score,
    ROUND(q.median_score, 1) AS median_score,
    ROUND(q.q75_score, 1) AS q75_score
FROM counts c
JOIN quantiles q USING (week_no)
ORDER BY c.week_no;
