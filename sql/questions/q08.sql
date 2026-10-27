-- Câu 8 (BR1): Môn nào có điểm TMA trung bình cao nhất và thấp nhất?
-- Đáp án chuẩn: Cao nhất EEE (81,2); thấp nhất GGG (68,5)
WITH tma_avg AS (
    SELECT
        a.code_module,
        COUNT(*) AS n_tma_submissions,
        ROUND(AVG(s.score), 1) AS avg_tma_score
    FROM fact_submission s
    JOIN dim_assessment a USING (id_assessment)
    WHERE a.assessment_type = 'TMA' 
      AND s.score IS NOT NULL
      AND NOT s.is_banked
    GROUP BY a.code_module
)
(
    SELECT code_module, n_tma_submissions, avg_tma_score, 'Highest' AS rank_type
    FROM tma_avg
    ORDER BY avg_tma_score DESC
    LIMIT 1
)
UNION ALL
(
    SELECT code_module, n_tma_submissions, avg_tma_score, 'Lowest' AS rank_type
    FROM tma_avg
    ORDER BY avg_tma_score ASC
    LIMIT 1
);
