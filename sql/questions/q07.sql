-- Câu 7 (BR1): Tỷ lệ nộp trễ chung của mọi TMA?
-- Đáp án chuẩn: 16,8% (16.320 bài)
SELECT
    COUNTIF(s.is_late) AS n_late_submissions,
    COUNTIF(NOT s.is_banked) AS n_regular_submissions,
    ROUND(100.0 * COUNTIF(s.is_late) / COUNTIF(NOT s.is_banked), 1) AS overall_tma_late_rate_pct
FROM fact_submission s
JOIN dim_assessment a USING (id_assessment)
WHERE a.assessment_type = 'TMA';
