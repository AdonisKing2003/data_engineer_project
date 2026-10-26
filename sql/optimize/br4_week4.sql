-- Việc 1.11, ví dụ 1: BR4 danh sách nguy cơ tại tuần 4, mọi đợt (câu 14).
-- Cùng logic với sql/bench/bq/star/br4_q14.sql, chỉ thêm dòng lọc hằng số p.week_no = 3.
-- Dòng đó không đổi kết quả (đã có p.week_no = w.week_no - 1 và w.week_no = 4) nhưng cho
-- BigQuery biết trước phía p chỉ cần phân vùng tuần 3. scripts/optimize.py bỏ dòng này để đo
-- bản "lọc qua phép nối" và đổi tên fact_student_week sang bảng đã phân vùng.
-- Đáp án: 27.250 lượt còn học; 3.958 vào danh sách; độ chính xác 80,6%; bao phủ 26,9%; nền 43,5%
WITH
cohort AS (
    SELECT
        w.id_student,
        w.code_module,
        w.code_presentation,
        w.week_no,
        w.clicks_cum,
        w.clicks_week,
        p.clicks_week AS clicks_prev_week,
        w.n_tma_missed_cum,
        w.avg_score_cum
    FROM fact_student_week AS w
    JOIN fact_student_week AS p
      ON p.id_student = w.id_student
     AND p.code_module = w.code_module
     AND p.code_presentation = w.code_presentation
     AND p.week_no = w.week_no - 1
    WHERE w.week_no = 4
      AND p.week_no = 3
      AND w.is_enrolled
),
cohort_with_p25 AS (
    SELECT
        c.*,
        PERCENTILE_CONT(CAST(c.clicks_cum AS FLOAT64), 0.25) OVER (
            PARTITION BY c.code_module, c.code_presentation
        ) AS p25
    FROM cohort AS c
),
scored AS (
    SELECT
        c.id_student,
        c.code_module,
        c.code_presentation,
        CASE WHEN c.clicks_cum < c.p25 THEN 1 ELSE 0 END
        + CASE WHEN c.clicks_week = 0 AND c.clicks_prev_week = 0 THEN 1 ELSE 0 END
        + CASE WHEN c.n_tma_missed_cum > 0 THEN 1 ELSE 0 END
        + CASE WHEN c.avg_score_cum < 40 THEN 1 ELSE 0 END AS risk
    FROM cohort_with_p25 AS c
),
labeled AS (
    SELECT
        s.risk >= 2 AS listed,
        label.final_result IN ('Fail', 'Withdrawn') AS bad
    FROM scored AS s
    JOIN fact_enrollment AS label
      ON label.id_student = s.id_student
     AND label.code_module = s.code_module
     AND label.code_presentation = s.code_presentation
)
SELECT
    COUNT(*) AS n_enrolled,
    SUM(CASE WHEN listed THEN 1 ELSE 0 END) AS n_listed,
    ROUND(100.0 * SUM(CASE WHEN listed AND bad THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN listed THEN 1 ELSE 0 END), 0), 1) AS precision_pct,
    ROUND(100.0 * SUM(CASE WHEN listed AND bad THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN bad THEN 1 ELSE 0 END), 0), 1) AS recall_pct,
    ROUND(100.0 * SUM(CASE WHEN bad THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS baseline_bad_rate_pct
FROM labeled
