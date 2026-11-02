-- Thống kê tổng quan kho dữ liệu (BigQuery)
SELECT 
    (SELECT COUNT(*) FROM dim_student) AS total_students,
    (SELECT COUNT(*) FROM fact_enrollment) AS total_enrollments,
    (SELECT COUNT(*) FROM dim_presentation) AS total_presentations,
    (SELECT COUNT(*) FROM dim_assessment) AS total_assessments;

