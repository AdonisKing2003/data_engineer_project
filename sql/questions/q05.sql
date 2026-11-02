-- Câu 5 (BR1): Tỷ lệ nộp bài 1752 của AAA 2013J?
-- Đáp án chuẩn: 96,5% (359 / 372)
-- Mẫu số: SV còn học tại hạn nộp, trừ SV có bài chuyển điểm (is_banked) cho bài này.
WITH assessment AS (
    SELECT code_module, code_presentation, deadline
    FROM dim_assessment
    WHERE id_assessment = 1752
),
eligible AS (
    SELECT e.id_student
    FROM fact_enrollment AS e
    JOIN assessment AS a
      ON a.code_module = e.code_module
     AND a.code_presentation = e.code_presentation
    WHERE (e.date_unregistration IS NULL OR e.date_unregistration > a.deadline)
      AND NOT EXISTS (
          SELECT 1
          FROM fact_submission AS b
          WHERE b.id_assessment = 1752
            AND b.id_student = e.id_student
            AND b.is_banked
      )
)
SELECT COUNT(*) AS mau_so,
       SUM(CASE WHEN s.id_student IS NOT NULL THEN 1 ELSE 0 END) AS da_nop,
       ROUND(100.0 * SUM(CASE WHEN s.id_student IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct
FROM eligible AS el
LEFT JOIN fact_submission AS s
  ON s.id_student = el.id_student
 AND s.id_assessment = 1752
 AND NOT s.is_banked
