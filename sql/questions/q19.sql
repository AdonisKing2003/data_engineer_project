-- Câu 19 (BR7): AAA 2014J tuần 10: trung vị tổng click từ đầu đợt của SV còn học?
-- Đáp án chuẩn: 593 click (336 SV)
-- Trung vị viết tay (trung bình hai phần tử giữa) để chạy được trên BigQuery, PostgreSQL, DuckDB.
WITH ranked AS (
    SELECT clicks_cum,
           ROW_NUMBER() OVER (ORDER BY clicks_cum) AS rn,
           COUNT(*) OVER () AS n
    FROM fact_student_week
    WHERE code_module = 'AAA'
      AND code_presentation = '2014J'
      AND week_no = 10
      AND is_enrolled
)
SELECT MAX(n) AS n_con_hoc,
       AVG(clicks_cum) AS trung_vi_clicks_cum
FROM ranked
WHERE rn IN (FLOOR((n + 1) / 2.0), CEIL((n + 1) / 2.0))
