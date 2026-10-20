-- Câu 12 (BR3): BR3 tính được cho bao nhiêu kỳ, và vì sao ít hơn tổng 22 kỳ?
-- Đáp án chuẩn: 19 kỳ có TMA đầu tiên có trọng số; 3 kỳ GGG không có TMA có trọng số.
WITH first_weighted_tma_presentations AS (
    SELECT DISTINCT code_module, code_presentation
    FROM dim_assessment
    WHERE assessment_type = 'TMA'
      AND weight > 0
      AND is_first_weighted_tma
)
SELECT
    COUNTIF(assessment.code_module IS NOT NULL) AS presentations_with_first_weighted_tma,
    COUNTIF(assessment.code_module IS NULL) AS presentations_without_first_weighted_tma,
    STRING_AGG(
        IF(
            assessment.code_module IS NULL,
            CONCAT(presentation.code_module, ' ', presentation.code_presentation),
            NULL
        ),
        ', ' ORDER BY presentation.code_module, presentation.code_presentation
    ) AS presentations_without_first_weighted_tma
FROM dim_presentation AS presentation
LEFT JOIN first_weighted_tma_presentations AS assessment
    ON assessment.code_module = presentation.code_module
   AND assessment.code_presentation = presentation.code_presentation;
