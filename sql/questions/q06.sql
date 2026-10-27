-- Câu 6 (BR1): TMA nào của BBB 2014J nộp trễ nhiều nhất?
-- Đáp án chuẩn: bài 15023 (hạn ngày 152), 22,1%
SELECT a.id_assessment,
       a.deadline,
       ROUND(100.0 * SUM(CASE WHEN s.is_late THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_tre
FROM fact_submission AS s
JOIN dim_assessment AS a ON a.id_assessment = s.id_assessment
WHERE a.code_module = 'BBB'
  AND a.code_presentation = '2014J'
  AND a.assessment_type = 'TMA'
  AND NOT s.is_banked
GROUP BY a.id_assessment, a.deadline
ORDER BY pct_tre DESC
LIMIT 1
