-- BR5: Đường cong rút lui tích lũy theo tuần của cả 22 đợt; trang lọc các đợt được chọn.
-- Mẫu số là mọi lượt đăng ký của đợt, tử số là lượt đã rút đến hết tuần (date_unregistration <= day_to).
WITH presentation_weeks AS (
    SELECT p.code_module, p.code_presentation,
           p.code_module || ' ' || p.code_presentation AS cohort,
           w.week_no, w.day_to
    FROM dim_presentation p
    CROSS JOIN dim_week w
    WHERE w.week_no >= -4 AND w.week_no < p.n_weeks
),
enrollment_base AS (
    SELECT code_module, code_presentation, COUNT(*) AS total_students
    FROM fact_enrollment
    GROUP BY code_module, code_presentation
),
weekly_dropouts AS (
    SELECT pw.code_module, pw.code_presentation, pw.cohort, pw.week_no, pw.day_to,
           SUM(CASE WHEN e.date_unregistration IS NOT NULL AND e.date_unregistration <= pw.day_to THEN 1 ELSE 0 END)
               AS cum_withdrawn_students
    FROM presentation_weeks pw
    LEFT JOIN fact_enrollment e
      ON e.code_module = pw.code_module AND e.code_presentation = pw.code_presentation
    GROUP BY pw.code_module, pw.code_presentation, pw.cohort, pw.week_no, pw.day_to
)
SELECT w.cohort, w.week_no, w.day_to, w.cum_withdrawn_students, b.total_students,
       ROUND(100.0 * w.cum_withdrawn_students / b.total_students, 2) AS cum_withdrawal_rate_pct,
       ROUND(100.0 * (b.total_students - w.cum_withdrawn_students) / b.total_students, 2) AS retention_rate_pct
FROM weekly_dropouts w
JOIN enrollment_base b
  ON b.code_module = w.code_module AND b.code_presentation = w.code_presentation
ORDER BY w.cohort, w.week_no
