-- TMA deadlines grouped into distinct course weeks for the selected offering.
SELECT DISTINCT
    CAST(FLOOR(deadline / 7.0) AS INTEGER) AS week_no
FROM read_parquet('data/warehouse/dim_assessment/*.parquet')
WHERE code_module = ?
  AND code_presentation = ?
  AND assessment_type = 'TMA'
  AND deadline IS NOT NULL
ORDER BY week_no;
