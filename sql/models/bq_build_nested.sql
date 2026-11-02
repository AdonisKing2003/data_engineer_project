-- Phần mô hình hóa, BigQuery dạng lồng: mỗi lượt đăng ký một dòng, các tuần nằm trong mảng weeks.
-- Cùng dữ liệu với fact_student_week (1.342.949 dòng phẳng) nhưng chỉ còn 32.593 dòng; khóa SV × đợt
-- lưu một lần thay vì lặp lại ở mỗi tuần. Mảng sắp theo week_no, phần tử đầu là tuần -4.
-- scripts/data_models.py thay {ds} bằng project.dataset.
CREATE OR REPLACE TABLE `{ds}.nested_student_timeline` AS
SELECT
    id_student,
    code_module,
    code_presentation,
    ARRAY_AGG(
        STRUCT(
            week_no,
            clicks_week,
            clicks_cum,
            active_days_week,
            sites_week,
            n_submitted_cum,
            n_late_cum,
            avg_score_cum,
            n_tma_missed_cum,
            is_pre_start,
            is_week_inactive,
            is_enrolled
        )
        ORDER BY week_no
    ) AS weeks
FROM `{ds}.fact_student_week`
GROUP BY id_student, code_module, code_presentation
