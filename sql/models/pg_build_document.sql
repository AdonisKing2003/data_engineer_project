-- Phần mô hình hóa, PostgreSQL dạng tài liệu: mỗi lượt đăng ký một tài liệu JSONB {"weeks": [...]},
-- giống cách một cơ sở dữ liệu tài liệu (MongoDB…) lưu hồ sơ học tập của một sinh viên.
-- Đặt ở schema riêng doc để không lẫn với kho star ở schema public.
DROP SCHEMA IF EXISTS doc CASCADE;
CREATE SCHEMA doc;

CREATE TABLE doc.student_timeline AS
SELECT
    id_student,
    code_module,
    code_presentation,
    jsonb_build_object(
        'weeks',
        jsonb_agg(
            jsonb_build_object(
                'week_no', week_no,
                'clicks_week', clicks_week,
                'clicks_cum', clicks_cum,
                'active_days_week', active_days_week,
                'sites_week', sites_week,
                'n_submitted_cum', n_submitted_cum,
                'n_late_cum', n_late_cum,
                'avg_score_cum', avg_score_cum,
                'n_tma_missed_cum', n_tma_missed_cum,
                'is_pre_start', is_pre_start,
                'is_week_inactive', is_week_inactive,
                'is_enrolled', is_enrolled
            )
            ORDER BY week_no
        )
    ) AS doc
FROM public.fact_student_week
GROUP BY id_student, code_module, code_presentation;

ALTER TABLE doc.student_timeline ADD PRIMARY KEY (id_student, code_module, code_presentation);
ANALYZE doc.student_timeline;
