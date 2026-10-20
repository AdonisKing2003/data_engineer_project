-- BR4 Q14 week 4 risk counts and precision benchmark variant (pg/star).
-- Benchmark-only: implements the checklist Q14 risk rule from tests/test_student_week.py; final_result is joined only after risk scoring, not TV2 accepted production SQL.
WITH
cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_cum,
        w.clicks_week,
        p.clicks_week AS clicks_prev_week,
        w.n_tma_missed_cum,
        w.avg_score_cum
    FROM fact_student_week AS w
    JOIN fact_student_week AS p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4
      AND w.is_enrolled
),
p25 AS (
    SELECT
        code_module,
        code_presentation,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY clicks_cum::double precision) AS p25
    FROM cohort
    GROUP BY code_module, code_presentation
),
cohort_with_p25 AS (
    SELECT c.*, p.p25
    FROM cohort AS c
    JOIN p25 AS p
      ON p.code_module = c.code_module
     AND p.code_presentation = c.code_presentation
),
scored AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        c.week_no,
        CASE WHEN c.clicks_cum < c.p25 THEN 1 ELSE 0 END
        + CASE WHEN c.clicks_week = 0 AND c.clicks_prev_week = 0 THEN 1 ELSE 0 END
        + CASE WHEN c.n_tma_missed_cum > 0 THEN 1 ELSE 0 END
        + CASE WHEN c.avg_score_cum < 40 THEN 1 ELSE 0 END AS risk
    FROM cohort_with_p25 AS c
),
labeled AS (
    SELECT
        s.id_student,
        s.code_module,
        s.code_presentation,
        s.risk >= 2 AS listed,
        label.final_result IN ('Fail', 'Withdrawn') AS bad
    FROM scored AS s
    JOIN fact_enrollment AS label
      ON label.id_student = s.id_student
     AND label.code_module = s.code_module
     AND label.code_presentation = s.code_presentation
)
SELECT
    COUNT(*) AS n_enrolled,
    SUM(CASE WHEN listed THEN 1 ELSE 0 END) AS n_listed,
    SUM(CASE WHEN listed AND bad THEN 1 ELSE 0 END) AS n_true_positives,
    ROUND(
        100.0 * SUM(CASE WHEN listed AND bad THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN listed THEN 1 ELSE 0 END), 0),
        1
    ) AS precision_pct,
    ROUND(
        100.0 * SUM(CASE WHEN listed AND bad THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN bad THEN 1 ELSE 0 END), 0),
        1
    ) AS recall_pct,
    ROUND(
        100.0 * SUM(CASE WHEN bad THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        1
    ) AS baseline_bad_rate_pct
FROM labeled;
