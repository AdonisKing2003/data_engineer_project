-- ==============================================================================
-- BR7 (BIGQUERY VERSION): THEO DÕI TIẾN ĐỘ CÁ NHÂN SO VỚI PHÂN VỊ LỚP
-- Cú pháp: GoogleSQL (BigQuery)
-- ==============================================================================

WITH cohort AS (
    SELECT
        id_student,
        clicks_cum,
        avg_score_cum,
        PERCENT_RANK() OVER (ORDER BY clicks_cum) * 100.0 AS click_percentile_rank,
        PERCENT_RANK() OVER (
            PARTITION BY (avg_score_cum IS NOT NULL) 
            ORDER BY avg_score_cum
        ) * 100.0 AS score_percentile_rank
    FROM `dataengineergroup32.oulad.fact_student_week`
    WHERE code_module = 'AAA' 
      AND code_presentation = '2014J'
      AND week_no = 10
      AND is_enrolled
),
cohort_summary AS (
    SELECT
        COUNT(*) AS total_students,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS q25_clicks,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)] AS q50_clicks,
        APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)] AS q75_clicks,
        APPROX_QUANTILES(avg_score_cum, 100)[OFFSET(50)] AS q50_score
    FROM `dataengineergroup32.oulad.fact_student_week`
    WHERE code_module = 'AAA' 
      AND code_presentation = '2014J'
      AND week_no = 10
      AND is_enrolled
)
SELECT
    c.id_student,
    c.clicks_cum AS student_clicks_cum,
    ROUND(c.click_percentile_rank, 1) AS click_percentile_pct,
    s.q25_clicks AS cohort_q25_clicks,
    s.q50_clicks AS cohort_median_clicks,
    s.q75_clicks AS cohort_q75_clicks,
    c.avg_score_cum AS student_avg_score,
    ROUND(c.score_percentile_rank, 1) AS score_percentile_pct,
    s.q50_score AS cohort_median_score,
    s.total_students AS total_active_peers
FROM cohort c
CROSS JOIN cohort_summary s
WHERE c.id_student = 32885;
