-- Câu 17 (BR5): Đợt nào có tỷ lệ Withdrawn cao nhất?
-- Đáp án chuẩn: CCC 2014B, 46,4%
SELECT
    code_module,
    code_presentation,
    COUNT(*) AS total_students,
    COUNTIF(is_withdrawn) AS withdrawn_students,
    ROUND(100.0 * COUNTIF(is_withdrawn) / COUNT(*), 1) AS withdrawal_rate_pct
FROM fact_enrollment
GROUP BY code_module, code_presentation
ORDER BY withdrawal_rate_pct DESC
LIMIT 1;
