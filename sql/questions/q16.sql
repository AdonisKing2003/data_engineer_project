-- Câu 16 (BR5): Ngày rút trung vị của sinh viên Withdrawn?
-- Đáp án chuẩn: Ngày 27
SELECT
    APPROX_QUANTILES(IF(is_withdrawn AND date_unregistration IS NOT NULL, date_unregistration, NULL), 100)[OFFSET(50)] AS median_unreg_day,
    APPROX_QUANTILES(IF(is_withdrawn AND date_unregistration IS NOT NULL, date_unregistration, NULL), 100)[OFFSET(25)] AS q25_unreg_day,
    APPROX_QUANTILES(IF(is_withdrawn AND date_unregistration IS NOT NULL, date_unregistration, NULL), 100)[OFFSET(75)] AS q75_unreg_day
FROM fact_enrollment;
