-- Offerings available in the local DuckDB/Parquet warehouse.
SELECT DISTINCT
    code_module,
    code_presentation
FROM read_parquet('data/warehouse/dim_presentation/*.parquet')
ORDER BY code_module, code_presentation;
