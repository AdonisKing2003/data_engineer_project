-- BR1 Q7 global TMA late rate benchmark variant (bq/3nf).
-- Benchmark-only: derives checklist Q7 from the contract is_late flag, TMA rows, and non-banked submissions; not TV2 accepted production SQL.
-- fact_submission is the contract view backed by physical fact_submission_n in this layout.
WITH totals AS (
    SELECT
        COUNT(*) AS tma_nonbanked_submissions,
        COUNTIF(s.is_late) AS late_submissions
    FROM fact_submission AS s
JOIN dim_assessment AS a
  ON a.id_assessment = s.id_assessment
WHERE a.assessment_type = 'TMA'
  AND NOT s.is_banked
)
SELECT
    tma_nonbanked_submissions,
    late_submissions,
    ROUND(
        100.0 * late_submissions / NULLIF(tma_nonbanked_submissions, 0),
        1
    ) AS late_rate_pct
FROM totals;
