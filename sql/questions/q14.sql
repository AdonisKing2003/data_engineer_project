-- Câu 14 (BR4): Tuần 4, mọi đợt: bao nhiêu SV vào danh sách nguy cơ, bao nhiêu % thật sự rớt/rút?
-- Đáp án chuẩn: 3.958 SV; 80,6% (tỷ lệ nền 43,5%)
-- Điểm nguy cơ 0–4 từ 4 dấu hiệu, vào danh sách khi >= 2. final_result chỉ nối vào sau khi chấm điểm.
-- P25 tính bằng nội suy tuyến tính (giống PERCENTILE_CONT) viết tay để chạy được trên BigQuery, PostgreSQL, DuckDB.
WITH cohort AS (
    SELECT w.id_student,
           w.code_module,
           w.code_presentation,
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
     AND p.week_no = 3
    WHERE w.week_no = 4
      AND w.is_enrolled
),
ranked AS (
    SELECT code_module,
           code_presentation,
           clicks_cum,
           ROW_NUMBER() OVER (PARTITION BY code_module, code_presentation ORDER BY clicks_cum) AS rn,
           1 + 0.25 * (COUNT(*) OVER (PARTITION BY code_module, code_presentation) - 1) AS pos
    FROM cohort
),
p25 AS (
    SELECT code_module,
           code_presentation,
           MAX(CASE WHEN rn = FLOOR(pos) THEN clicks_cum END)
           + (MAX(pos) - FLOOR(MAX(pos)))
             * (MAX(CASE WHEN rn = CEIL(pos) THEN clicks_cum END) - MAX(CASE WHEN rn = FLOOR(pos) THEN clicks_cum END))
             AS p25_clicks
    FROM ranked
    GROUP BY code_module, code_presentation
),
scored AS (
    SELECT c.id_student,
           c.code_module,
           c.code_presentation,
           CASE WHEN c.clicks_cum < q.p25_clicks THEN 1 ELSE 0 END
           + CASE WHEN c.clicks_week = 0 AND c.clicks_prev_week = 0 THEN 1 ELSE 0 END
           + CASE WHEN c.n_tma_missed_cum > 0 THEN 1 ELSE 0 END
           + CASE WHEN c.avg_score_cum < 40 THEN 1 ELSE 0 END AS risk
    FROM cohort AS c
    JOIN p25 AS q
      ON q.code_module = c.code_module
     AND q.code_presentation = c.code_presentation
),
labeled AS (
    SELECT CASE WHEN s.risk >= 2 THEN 1 ELSE 0 END AS listed,
           CASE WHEN e.final_result IN ('Fail', 'Withdrawn') THEN 1 ELSE 0 END AS bad
    FROM scored AS s
    JOIN fact_enrollment AS e
      ON e.id_student = s.id_student
     AND e.code_module = s.code_module
     AND e.code_presentation = s.code_presentation
)
SELECT COUNT(*) AS n_con_hoc,
       SUM(listed) AS n_vao_danh_sach,
       ROUND(100.0 * SUM(listed * bad) / SUM(listed), 1) AS do_chinh_xac_pct,
       ROUND(100.0 * SUM(bad) / COUNT(*), 1) AS ty_le_nen_pct
FROM labeled
