-- Phần mô hình hóa: BR4 tuần 4 (câu 14) trên bảng dạng lồng nested_student_timeline.
-- Bản phẳng (sql/optimize/br4_week4.sql) phải nối fact_student_week với chính nó để lấy click tuần 3.
-- Ở đây tuần 3 và tuần 4 nằm cùng một dòng, nên chỉ cần một truy vấn con trên mảng của chính dòng đó.
-- Đáp án: 27.250 lượt còn học; 3.958 vào danh sách; độ chính xác 80,6%; bao phủ 26,9%; nền 43,5%
WITH
cohort AS (
    SELECT
        t.id_student,
        t.code_module,
        t.code_presentation,
        w.clicks_cum,
        w.clicks_week,
        (SELECT p.clicks_week FROM UNNEST(t.weeks) AS p WHERE p.week_no = 3) AS clicks_prev_week,
        w.n_tma_missed_cum,
        w.avg_score_cum
    FROM nested_student_timeline AS t, UNNEST(t.weeks) AS w
    WHERE w.week_no = 4
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
