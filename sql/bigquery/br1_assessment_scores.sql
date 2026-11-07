-- BR1 detail: Điểm số chi tiết từng bài kiểm tra cho biểu đồ Box Plot (BigQuery)
SELECT 
    a.assessment_type || ' ' || CAST(a.id_assessment AS STRING) AS assessment_label,
    a.deadline,
    s.score
FROM dim_assessment a
JOIN fact_submission s USING (id_assessment)
WHERE a.code_module = @code_module AND a.code_presentation = @code_presentation
  AND s.score IS NOT NULL
ORDER BY a.deadline, a.id_assessment;

