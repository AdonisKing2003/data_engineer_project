-- Câu 17 (BR5): Đợt nào có tỷ lệ Withdrawn cao nhất?
-- Đáp án chuẩn: CCC 2014B, 46,4%
SELECT code_module,
       code_presentation,
       ROUND(100.0 * SUM(CASE WHEN is_withdrawn THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_withdrawn
FROM fact_enrollment
GROUP BY code_module, code_presentation
ORDER BY pct_withdrawn DESC
LIMIT 1
