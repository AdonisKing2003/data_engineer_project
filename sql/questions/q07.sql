-- Câu 7 (BR1): Tỷ lệ nộp trễ chung của mọi TMA?
-- Đáp án chuẩn: 16,8% (16.320 bài)
SELECT SUM(CASE WHEN s.is_late THEN 1 ELSE 0 END) AS n_tre,
       ROUND(100.0 * SUM(CASE WHEN s.is_late THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct
FROM fact_submission AS s
JOIN dim_assessment AS a ON a.id_assessment = s.id_assessment
WHERE a.assessment_type = 'TMA'
  AND NOT s.is_banked
