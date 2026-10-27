-- Câu 6 (BR1): TMA nào của BBB 2014J có tỷ lệ nộp trễ cao nhất?
-- Đáp án chuẩn: Bài 15023 (hạn ngày 152), 22,1%
SELECT
    a.id_assessment,
    a.assessment_order,
    a.deadline,
    COUNT(*) AS total_submissions,
    COUNTIF(s.is_late) AS late_submissions,
    ROUND(100.0 * COUNTIF(s.is_late) / COUNTIF(NOT s.is_banked), 1) AS late_rate_pct
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.code_module = 'BBB' 
  AND a.code_presentation = '2014J' 
  AND a.assessment_type = 'TMA'
GROUP BY a.id_assessment, a.assessment_order, a.deadline
ORDER BY late_rate_pct DESC
LIMIT 1;
