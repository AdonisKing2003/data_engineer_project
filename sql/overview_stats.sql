-- Overview page: warehouse-wide headline counts (one row).
-- total_clicks sums fact_enrollment.total_clicks, which equals SUM(sum_click) of fact_vle_daily.
SELECT
    (SELECT COUNT(DISTINCT code_module)
       FROM read_parquet('data/warehouse/dim_presentation/*.parquet')) AS n_modules,
    (SELECT COUNT(*)
       FROM read_parquet('data/warehouse/dim_presentation/*.parquet')) AS n_offerings,
    (SELECT COUNT(DISTINCT id_student)
       FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')) AS n_students,
    (SELECT COUNT(*)
       FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')) AS n_enrollments,
    (SELECT COUNT(*)
       FROM read_parquet('data/warehouse/fact_submission/*.parquet')) AS n_submissions,
    (SELECT SUM(total_clicks)
       FROM read_parquet('data/warehouse/fact_enrollment/*.parquet')) AS total_clicks;
