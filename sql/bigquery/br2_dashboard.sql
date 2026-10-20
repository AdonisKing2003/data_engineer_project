-- Home contract: selected offering's weekly chart fields and cohort-based click averages.
SELECT
    week_no,
    activity_type,
    activity_type_click_share,
    activity_type_total_clicks,
    enrolled_students,
    avg_clicks_per_enrolled_student,
    activity_type_avg_clicks_per_enrolled_student
FROM tv3_br2_weekly_mart
WHERE code_module = @code_module
  AND code_presentation = @code_presentation
ORDER BY week_no, activity_type;
