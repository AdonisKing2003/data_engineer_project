-- Overview page: warehouse-wide headline counts (one row).
-- total_clicks sums fact_enrollment.total_clicks, which equals SUM(sum_click) of fact_vle_daily.
SELECT
    (SELECT COUNT(DISTINCT code_module) FROM dim_presentation) AS n_modules,
    (SELECT COUNT(*) FROM dim_presentation) AS n_offerings,
    (SELECT COUNT(DISTINCT id_student) FROM fact_enrollment) AS n_students,
    (SELECT COUNT(*) FROM fact_enrollment) AS n_enrollments,
    (SELECT COUNT(*) FROM fact_submission) AS n_submissions,
    (SELECT SUM(total_clicks) FROM fact_enrollment) AS total_clicks;
