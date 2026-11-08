-- BR8: click của một sinh viên trong một tuần, theo từng loại học liệu, đặt cạnh dải 25%-75%
-- click của nhóm đạt (Pass/Distinction) cùng đợt. Ai trong nhóm đạt không click loại đó trong
-- tuần được tính là 0, như câu hỏi mẫu 20.
-- Tham số theo thứ tự: code_module, code_presentation, week_no, id_student.
WITH params AS (
    SELECT
        CAST(? AS VARCHAR) AS code_module,
        CAST(? AS VARCHAR) AS code_presentation,
        CAST(? AS INTEGER) AS week_no,
        CAST(? AS BIGINT) AS id_student
), activity_types AS (
    SELECT DISTINCT site.activity_type
    FROM dim_vle_site AS site
    INNER JOIN params
        ON site.code_module = params.code_module
       AND site.code_presentation = params.code_presentation
), pass_group AS (
    SELECT enrollment.id_student
    FROM fact_enrollment AS enrollment
    INNER JOIN params
        ON enrollment.code_module = params.code_module
       AND enrollment.code_presentation = params.code_presentation
    WHERE enrollment.final_result IN ('Pass', 'Distinction')
), week_clicks AS (
    SELECT
        vle.id_student,
        site.activity_type,
        SUM(vle.sum_click) AS clicks
    FROM fact_vle_daily AS vle
    INNER JOIN params
        ON vle.code_module = params.code_module
       AND vle.code_presentation = params.code_presentation
       AND vle.week_no = params.week_no
    INNER JOIN dim_vle_site AS site
        ON site.id_site = vle.id_site
       AND site.code_module = vle.code_module
       AND site.code_presentation = vle.code_presentation
    WHERE NOT vle.is_pre_start
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
    SELECT
        activity_type,
        COUNT(*) AS n_pass_students,
        quantile_cont(clicks, 0.25) AS q25_clicks,
        quantile_cont(clicks, 0.5) AS median_clicks,
        quantile_cont(clicks, 0.75) AS q75_clicks
    FROM pass_clicks
    GROUP BY activity_type
)
SELECT
    summary.activity_type,
    summary.n_pass_students,
    summary.q25_clicks,
    summary.median_clicks,
    summary.q75_clicks,
    COALESCE(own.clicks, 0) AS student_clicks
FROM pass_summary AS summary
CROSS JOIN params
LEFT JOIN week_clicks AS own
    ON own.activity_type = summary.activity_type
   AND own.id_student = params.id_student
ORDER BY summary.median_clicks DESC, summary.activity_type;
