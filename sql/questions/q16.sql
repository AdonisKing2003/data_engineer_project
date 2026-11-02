-- Câu 16 (BR5): Ngày rút trung vị của SV Withdrawn?
-- Đáp án chuẩn: ngày 27
-- Trung vị viết tay (trung bình hai phần tử giữa) để chạy được trên BigQuery, PostgreSQL, DuckDB.
WITH ranked AS (
    SELECT date_unregistration AS d,
           ROW_NUMBER() OVER (ORDER BY date_unregistration) AS rn,
           COUNT(*) OVER () AS n
    FROM fact_enrollment
    WHERE is_withdrawn
      AND date_unregistration IS NOT NULL
)
SELECT MAX(n) AS n_withdrawn_co_ngay_rut,
       AVG(d) AS ngay_rut_trung_vi
FROM ranked
WHERE rn IN (FLOOR((n + 1) / 2.0), CEIL((n + 1) / 2.0))
