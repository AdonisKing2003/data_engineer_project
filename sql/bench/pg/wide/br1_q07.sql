-- BR1 Q7 global TMA late rate benchmark variant (pg/wide).
-- Benchmark-only: derives checklist Q7 from the contract is_late flag, TMA rows, and non-banked submissions; not TV2 accepted production SQL.
WITH totals AS (
    SELECT
        COUNT(*) AS tma_nonbanked_submissions,
        COUNT(*) FILTER (WHERE s.is_late) AS late_submissions
    FROM wide_submission AS s
WHERE s.assessment_type = 'TMA'
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
