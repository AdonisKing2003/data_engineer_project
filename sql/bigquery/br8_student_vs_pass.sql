-- BR8: click của một sinh viên trong một tuần, theo từng loại học liệu, đặt cạnh dải 25%-75%
-- click của nhóm đạt (Pass/Distinction) cùng đợt. Ai trong nhóm đạt không click loại đó trong
-- tuần được tính là 0, như câu hỏi mẫu 20.
-- Lọc bảng click bằng tham số trực tiếp (không qua phép nối) để BigQuery dùng được gom cụm
-- theo đợt và chỉ đọc phần bảng của đợt đó.
WITH activity_types AS (
    SELECT DISTINCT activity_type
    FROM dim_vle_site
    WHERE code_module = @code_module
      AND code_presentation = @code_presentation
), pass_group AS (
    SELECT id_student
    FROM fact_enrollment
    WHERE code_module = @code_module
      AND code_presentation = @code_presentation
      AND final_result IN ('Pass', 'Distinction')
), week_clicks AS (
    SELECT
        vle.id_student,
        site.activity_type,
        SUM(vle.sum_click) AS clicks
    FROM fact_vle_daily AS vle
    INNER JOIN dim_vle_site AS site
        ON site.id_site = vle.id_site
       AND site.code_module = vle.code_module
       AND site.code_presentation = vle.code_presentation
    WHERE vle.code_module = @code_module
      AND vle.code_presentation = @code_presentation
      AND vle.week_no = @week_no
      AND NOT vle.is_pre_start
    GROUP BY vle.id_student, site.activity_type
), pass_clicks AS (
    SELECT
        types.activity_type,
        pass_group.id_student,
        COALESCE(week_clicks.clicks, 0) AS clicks
    FROM activity_types AS types
    CROSS JOIN pass_group
    LEFT JOIN week_clicks
        ON week_clicks.id_student = pass_group.id_student
       AND week_clicks.activity_type = types.activity_type
), pass_summary AS (
    SELECT DISTINCT
        activity_type,
        COUNT(*) OVER (PARTITION BY activity_type) AS n_pass_students,
        PERCENTILE_CONT(clicks, 0.25) OVER (PARTITION BY activity_type) AS q25_clicks,
        PERCENTILE_CONT(clicks, 0.5) OVER (PARTITION BY activity_type) AS median_clicks,
        PERCENTILE_CONT(clicks, 0.75) OVER (PARTITION BY activity_type) AS q75_clicks
    FROM pass_clicks
)
SELECT
    summary.activity_type,
    summary.n_pass_students,
    summary.q25_clicks,
    summary.median_clicks,
    summary.q75_clicks,
    COALESCE(own.clicks, 0) AS student_clicks
FROM pass_summary AS summary
LEFT JOIN week_clicks AS own
    ON own.activity_type = summary.activity_type
   AND own.id_student = @id_student
ORDER BY summary.median_clicks DESC, summary.activity_type;
