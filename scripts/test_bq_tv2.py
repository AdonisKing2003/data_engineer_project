import os
from google.cloud import bigquery

project = os.environ.get("GCP_PROJECT_ID", "dataengineergroup32")
dataset = os.environ.get("BQ_DATASET", "oulad")
client = bigquery.Client(project=project)

print(f"Connecting to BigQuery project: {project}, dataset: {dataset}...")

# 1. Test BR1 query on BigQuery: Bài 1752
q_br1 = f"""
SELECT
    s.id_assessment,
    COUNT(DISTINCT s.id_student) AS n_submitted,
    ROUND(100.0 * COUNT(DISTINCT s.id_student) / e.active_students, 1) AS submission_rate_pct,
    ROUND(100.0 * COUNTIF(s.is_late) / COUNTIF(NOT s.is_banked), 1) AS late_rate_pct,
    APPROX_QUANTILES(s.score, 2)[OFFSET(1)] AS median_score
FROM `{project}.{dataset}.fact_submission` s
CROSS JOIN (
    SELECT COUNT(DISTINCT e.id_student) AS active_students
    FROM `{project}.{dataset}.fact_enrollment` e
    JOIN `{project}.{dataset}.dim_assessment` a ON a.id_assessment = 1752
    WHERE e.code_module = a.code_module 
      AND e.code_presentation = a.code_presentation
      AND (e.date_unregistration IS NULL OR e.date_unregistration > a.deadline)
) e
WHERE s.id_assessment = 1752
GROUP BY s.id_assessment, e.active_students
"""
row1 = list(client.query(q_br1).result())[0]
print(f"BR1 (1752) on BigQuery: sub_rate={row1.submission_rate_pct}%, late_rate={row1.late_rate_pct}%, median={row1.median_score}")

# 2. Test BR5 query on BigQuery: CCC 2014B withdrawal
q_br5 = f"""
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS total_students,
    COUNTIF(is_withdrawn) AS withdrawn_students,
    ROUND(100.0 * COUNTIF(is_withdrawn) / COUNT(*), 1) AS withdrawal_rate_pct
FROM `{project}.{dataset}.fact_enrollment`
WHERE code_module = 'CCC' AND code_presentation = '2014B'
GROUP BY code_module, code_presentation
"""
row5 = list(client.query(q_br5).result())[0]
print(f"BR5 (CCC 2014B) on BigQuery: total={row5.total_students}, withdrawn={row5.withdrawn_students}, rate={row5.withdrawal_rate_pct}%")

# 3. Test BR7 query on BigQuery: AAA 2014J week 10 quantiles
q_br7 = f"""
SELECT
    COUNT(*) AS n_active_students,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS q25,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(50)] AS q50,
    APPROX_QUANTILES(clicks_cum, 100)[OFFSET(75)] AS q75
FROM `{project}.{dataset}.fact_student_week`
WHERE code_module = 'AAA' 
  AND code_presentation = '2014J' 
  AND week_no = 10 
  AND is_enrolled
"""
row7 = list(client.query(q_br7).result())[0]
print(f"BR7 (AAA 2014J w10) on BigQuery: n={row7.n_active_students}, Q25={row7.q25}, Q50={row7.q50}, Q75={row7.q75}")

# 4. Test BR4 query on BigQuery: Week 4 at-risk count
q_br4 = f"""
WITH cohort AS (
    SELECT
        w.id_student, w.code_module, w.code_presentation,
        w.clicks_cum, w.clicks_week, w.avg_score_cum, w.n_tma_missed_cum,
        p.clicks_week AS clicks_prev_week
    FROM `{project}.{dataset}.fact_student_week` w
    LEFT JOIN `{project}.{dataset}.fact_student_week` p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4 AND w.is_enrolled
),
p25 AS (
    SELECT code_module, code_presentation, APPROX_QUANTILES(clicks_cum, 100)[OFFSET(25)] AS p25_clicks
    FROM cohort GROUP BY code_module, code_presentation
),
scored AS (
    SELECT
        c.id_student, c.code_module, c.code_presentation,
        (CAST(c.clicks_cum < p.p25_clicks AS INT64) +
         CAST(c.clicks_week = 0 AND COALESCE(c.clicks_prev_week, 0) = 0 AS INT64) +
         CAST(c.n_tma_missed_cum > 0 AS INT64) +
         CAST(COALESCE(c.avg_score_cum < 40, FALSE) AS INT64)) >= 2 AS is_at_risk
    FROM cohort c JOIN p25 p USING (code_module, code_presentation)
),
labeled AS (
    SELECT s.is_at_risk, (e.final_result IN ('Fail', 'Withdrawn')) AS bad
    FROM scored s JOIN `{project}.{dataset}.fact_enrollment` e USING (id_student, code_module, code_presentation)
)
SELECT
    COUNT(*) AS total_students,
    COUNTIF(is_at_risk) AS n_flagged,
    ROUND(100.0 * COUNTIF(is_at_risk AND bad) / COUNTIF(is_at_risk), 1) AS precision_pct,
    ROUND(100.0 * COUNTIF(is_at_risk AND bad) / COUNTIF(bad), 1) AS recall_pct,
    ROUND(100.0 * COUNTIF(bad) / COUNT(*), 1) AS base_rate_pct
FROM labeled
"""
row4 = list(client.query(q_br4).result())[0]
print(f"BR4 (Week 4 all presentations) on BigQuery: flagged={row4.n_flagged}, precision={row4.precision_pct}%, recall={row4.recall_pct}%, base={row4.base_rate_pct}%")
print("\n>>> ALL 4 BRs EXECUTED PERFECTLY ON BIGQUERY! <<<")
