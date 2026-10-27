-- Câu 8 (BR1): Môn nào có điểm TMA trung bình cao nhất, thấp nhất?
-- Đáp án chuẩn: cao nhất EEE (81,2); thấp nhất GGG (68,5). Dòng đầu là cao nhất, dòng cuối là thấp nhất.
SELECT a.code_module,
       ROUND(AVG(s.score), 1) AS diem_tb
FROM fact_submission AS s
JOIN dim_assessment AS a ON a.id_assessment = s.id_assessment
WHERE a.assessment_type = 'TMA'
  AND NOT s.is_banked
GROUP BY a.code_module
ORDER BY diem_tb DESC
