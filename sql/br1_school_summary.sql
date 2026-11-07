-- BR1 toàn trường: bài TMA theo môn, dùng cho câu 7 (tỷ lệ nộp trễ chung) và câu 8 (điểm TMA trung bình theo môn).
-- Như BR1: bỏ bài chuyển điểm (is_banked); trễ chỉ tính TMA. Trang cộng n_late / n_tma_submissions để ra tỷ lệ chung.
-- Viết bằng SQL chung nên file DuckDB và BigQuery giống nhau.
SELECT a.code_module,
       COUNT(*) AS n_tma_submissions,
       SUM(CASE WHEN s.is_late THEN 1 ELSE 0 END) AS n_late,
       COUNT(s.score) AS n_scored,
       AVG(s.score) AS avg_score
FROM fact_submission AS s
JOIN dim_assessment AS a ON a.id_assessment = s.id_assessment
WHERE a.assessment_type = 'TMA'
  AND NOT s.is_banked
GROUP BY a.code_module
ORDER BY a.code_module
