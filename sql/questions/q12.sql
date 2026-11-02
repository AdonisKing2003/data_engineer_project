-- Câu 12 (BR3): BR3 tính được cho bao nhiêu kỳ, và vì sao ít hơn tổng 22 kỳ?
-- Đáp án chuẩn: 19 kỳ có TMA đầu tiên có trọng số; 3 kỳ GGG không có TMA có trọng số.
-- Viết bằng SUM(CASE ...) và || thay cho COUNTIF, IF, CONCAT để chạy được trên BigQuery, PostgreSQL, DuckDB.
WITH first_weighted_tma_presentations AS (
    SELECT DISTINCT code_module, code_presentation
    FROM dim_assessment
    WHERE assessment_type = 'TMA'
      AND weight > 0
      AND is_first_weighted_tma
)
SELECT
    SUM(CASE WHEN assessment.code_module IS NOT NULL THEN 1 ELSE 0 END) AS presentations_with_first_weighted_tma,
    SUM(CASE WHEN assessment.code_module IS NULL THEN 1 ELSE 0 END) AS presentations_without_first_weighted_tma,
    STRING_AGG(
        CASE
            WHEN assessment.code_module IS NULL
            THEN presentation.code_module || ' ' || presentation.code_presentation
        END,
        ', ' ORDER BY presentation.code_module, presentation.code_presentation
    ) AS presentations_without_first_weighted_tma_list
FROM dim_presentation AS presentation
LEFT JOIN first_weighted_tma_presentations AS assessment
    ON assessment.code_module = presentation.code_module
   AND assessment.code_presentation = presentation.code_presentation
