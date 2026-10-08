# Hợp đồng tên bảng và tên cột

File này là "hợp đồng" giữa người dựng kho (TV1) và người viết SQL (TV2, TV3).
TV1 tạo đúng các bảng, cột, kiểu dưới đây; TV2, TV3 viết SQL theo đúng các tên này.

**Nguồn:** sheet Task1, Task2, Fact, Dimension, Cờ (file `Database project.xlsx`) và tài liệu
"OULAD – Giai đoạn 2: Đặc tả 8 BR" (Phụ lục kỹ thuật + 6 quyết định).
Cột **Kiểm** là số dòng TRUE (với cờ) hoặc số dòng của bảng. Mọi con số trong cột này đã được
đếm lại trên dữ liệu staging ngày 08/10 và khớp với sheet. Đây cũng là tiêu chí nghiệm thu cho ETL và pytest.

**Trạng thái:** ĐÃ CHỐT ngày 08/10/2026. Các quyết định đã chốt ghi ở [mục 6](#6-quyết-định-đã-chốt).
File này thay cho sheet Fact / Dimension / Cờ: chỗ nào sheet ghi khác thì theo file này.

---

## 1. Quy ước chung

| Quy ước | Nội dung |
|---|---|
| Tên | chữ thường, `snake_case`. Dimension bắt đầu bằng `dim_`, fact bằng `fact_`, cờ bằng `is_` / `has_` hoặc tên mô tả (`score_missing`, `zero_weight`…) theo sheet Cờ |
| Khóa | Giữ khóa gốc của OULAD, không tạo surrogate key: `id_student`, `id_assessment`, `id_site`, và cặp `code_module` + `code_presentation` cho một đợt |
| Ngày | Số nguyên, số ngày tính từ ngày khai giảng (ngày 0). Âm = trước khai giảng |
| Tuần | `week_no = CAST(FLOOR(date / 7) AS INT64)`; tuần `w` là các ngày `7w` đến `7w + 6`. **Không dùng `date // 7` (DuckDB) hay `DIV(date, 7)` (BigQuery)**: hai cách này làm tròn về 0, nên ngày −1 thành tuần 0 |
| Cờ | Kiểu `BOOL`, luôn TRUE/FALSE. Ngoại lệ duy nhất: `is_pass_score` là NULL khi thiếu điểm |
| Giá trị thiếu | `NULL`. Ngoại lệ: `imd_band` thiếu thì ghi `'Unknown'` (kèm cờ `imd_unknown`) |
| Không xóa dữ liệu | Không xóa dòng, không sửa giá trị gốc. Chỗ nào có vấn đề thì thêm cờ (nguyên tắc sheet Task1) |
| Nơi lưu | BigQuery: dataset `oulad`. PostgreSQL: schema `public`, cùng tên. Parquet: `data/warehouse/<bảng>/` |

Kiểu ghi theo BigQuery: `INT64`, `FLOAT64`, `STRING`, `BOOL`.
PostgreSQL tương ứng: `BIGINT`, `DOUBLE PRECISION`, `TEXT`, `BOOLEAN`.

### Định nghĩa dùng chung (Phụ lục kỹ thuật)

| Khái niệm | Điều kiện chính xác |
|---|---|
| Còn học tại ngày `t` | `date_unregistration IS NULL OR date_unregistration > t` |
| Rút trước khai giảng | `date_unregistration <= 0` (cờ `withdrawn_before_start`) |
| Ngày cuối tuần `w` | `e = 7w + 6` |
| Đạt môn | `final_result IN ('Pass', 'Distinction')` |
| Đạt một bài | `score >= 40` |

---

## 2. Dimension

### `dim_presentation`: một dòng cho một đợt (Kiểm: 22 dòng)

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `code_module`, `code_presentation` | STRING | Khóa ghép | |
| `year` | INT64 | 4 ký tự đầu của `code_presentation` | |
| `semester` | STRING | `B` (bắt đầu tháng 2) hoặc `J` (tháng 10) | |
| `length_days` | INT64 | `module_presentation_length` gốc (234..269) | |
| `n_weeks` | INT64 | `FLOOR((length_days − 1) / 7) + 1` (34..39) | |
| `has_exam_result` | BOOL | Có ít nhất 1 bài nộp Exam (chỉ CCC, DDD) | 6 |
| `has_weighted_tma` | BOOL | Có TMA `weight > 0` (GGG không có) | 19 |

### `dim_student`: một dòng cho một sinh viên (Kiểm: 28.785 dòng)

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_student` | INT64 | Khóa | |
| `gender`, `region`, `highest_education`, `disability` | STRING | Không đổi giữa các đợt (đã kiểm) | |
| `imd_band` | STRING | Sửa `10-20` thành `10-20%`; NULL thành `'Unknown'` | |
| `imd_unknown` | BOOL | `imd_band` gốc NULL | 971 SV (1.111 lượt đăng ký) |

`age_band` **không** ở đây vì 72 SV đổi nhóm tuổi giữa các đợt, nó nằm ở `fact_enrollment`.

### `dim_assessment`: một dòng cho một bài (Kiểm: 206 dòng)

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_assessment` | INT64 | Khóa | |
| `code_module`, `code_presentation` | STRING | FK → `dim_presentation` | |
| `assessment_type` | STRING | `TMA` / `CMA` / `Exam` | 106 / 76 / 24 |
| `deadline_raw` | INT64 | Cột `date` gốc | 11 NULL, đều là Exam |
| `deadline` | INT64 | `COALESCE(date, length_days)` | |
| `weight` | FLOAT64 | Trọng số % | |
| `assessment_order` | INT64 | Thứ tự trong đợt theo `deadline`, rồi `id_assessment` | |
| `deadline_imputed` | BOOL | `date` gốc NULL | 11 |
| `zero_weight` | BOOL | `weight = 0` | 56 |
| `is_first_weighted_tma` | BOOL | TMA `weight > 0` có `deadline` nhỏ nhất trong đợt; hòa thì lấy `id_assessment` nhỏ nhất (vd BBB 2014J là bài 15021) | 19 |
| `has_submissions` | BOOL | Có ít nhất 1 dòng trong `fact_submission` | 188 |

### `dim_vle_site`: một dòng cho một học liệu (Kiểm: 6.364 dòng)

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_site` | INT64 | Khóa | |
| `code_module`, `code_presentation` | STRING | FK → `dim_presentation` | |
| `activity_type` | STRING | 20 loại | |
| `week_from`, `week_to` | INT64 | Tuần dự kiến, 82,4% NULL. Không dùng làm đặc trưng | |
| `has_planned_week` | BOOL | `week_from IS NOT NULL` | 1.121 |
| `never_clicked` | BOOL | Không có click nào | 96 |

### `dim_week`: một dòng cho một tuần (Kiểm: 43 dòng, tuần −4..38)

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `week_no` | INT64 | Khóa | |
| `day_from`, `day_to` | INT64 | `week_no * 7` và `week_no * 7 + 6` | |
| `is_pre_start` | BOOL | `week_no < 0` | 4 |

---

## 3. Fact

### `fact_vle_daily`: click theo SV × đợt × học liệu × ngày (Kiểm: 8.459.320 dòng)

CSV gốc có 10.655.280 dòng; các dòng trùng khóa được gộp bằng cách cộng `sum_click`.

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_student` | INT64 | FK → `dim_student` | |
| `code_module`, `code_presentation` | STRING | FK → `dim_presentation` | |
| `id_site` | INT64 | FK → `dim_vle_site` | |
| `date` | INT64 | −25..269 | |
| `week_no` | INT64 | FK → `dim_week` | |
| `sum_click` | INT64 | Tổng click các dòng gốc cùng khóa. Tổng toàn bảng = 39.605.099 | |
| `n_records` | INT64 | Số dòng gốc đã gộp | >1 ở 1.614.505 dòng |
| `is_pre_start` | BOOL | `date < 0` | 600.241 |

### `fact_submission`: một dòng cho một lần nộp (Kiểm: 173.912 dòng)

Grain: (`id_student`, `id_assessment`).

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_student` | INT64 | FK → `dim_student` | |
| `id_assessment` | INT64 | FK → `dim_assessment` | |
| `code_module`, `code_presentation` | STRING | Lấy từ `dim_assessment` | |
| `date_submitted` | INT64 | −11..608 | |
| `week_no` | INT64 | Tuần của `date_submitted` | |
| `score` | INT64 | 0–100, NULL nếu thiếu (mọi điểm đều là số nguyên) | |
| `days_late` | INT64 | `date_submitted − dim_assessment.deadline`; NULL nếu `is_banked` | |
| `is_banked` | BOOL | Cột gốc `is_banked = 1` | 1.909 |
| `is_late` | BOOL | `assessment_type = 'TMA' AND NOT is_banked AND date_submitted > deadline` (chỉ TMA, xem mục 6) | 16.320 |
| `score_missing` | BOOL | `score IS NULL` | 173 |
| `is_beyond_course` | BOOL | `date_submitted > length_days` | 85 |
| `is_pass_score` | BOOL | `score >= 40`, NULL khi thiếu điểm | 166.161 |

### `fact_enrollment`: một dòng cho một lượt đăng ký (Kiểm: 32.593 dòng)

Grain: (`id_student`, `code_module`, `code_presentation`).

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_student` | INT64 | FK → `dim_student` | |
| `code_module`, `code_presentation` | STRING | FK → `dim_presentation` | |
| `final_result` | STRING | Pass / Fail / Withdrawn / Distinction. **Chỉ dùng làm nhãn để chấm BR4, không dùng làm đặc trưng** | |
| `age_band` | STRING | Theo từng lượt (72 SV đổi nhóm tuổi) | |
| `studied_credits` | INT64 | 30..655 | |
| `num_of_prev_attempts` | INT64 | 0..6 | |
| `date_registration` | INT64 | −322..167 | 45 NULL |
| `date_unregistration` | INT64 | −365..444, NULL = không rút | |
| `total_clicks` | INT64 | Tổng `sum_click` cả đợt, 0 nếu không click | |
| `active_days` | INT64 | Số ngày khác nhau có click | |
| `n_submissions` | INT64 | Số bài đã nộp | |
| `is_withdrawn` | BOOL | `final_result = 'Withdrawn'` | 10.156 |
| `withdrawn_before_start` | BOOL | `date_unregistration <= 0` | 3.097 |
| `no_vle_activity` | BOOL | Không có dòng nào trong `fact_vle_daily` | 3.365 |
| `reg_date_missing` | BOOL | `date_registration IS NULL` | 45 |
| `result_inconsistent` | BOOL | `(final_result = 'Withdrawn') <> (date_unregistration IS NOT NULL)` | 102 |
| `is_repeat` | BOOL | `num_of_prev_attempts > 0` | 4.172 |

### `fact_student_week`: ảnh chụp SV × đợt × tuần (Kiểm: 1.342.949 dòng)

Grain: (`id_student`, `code_module`, `code_presentation`, `week_no`).
**Mỗi lượt đăng ký có đủ các tuần từ −4 đến `n_weeks − 1`**, kể cả sau khi rút. Lọc người còn học bằng `is_enrolled`.
Quy tắc as-of: cột của tuần `w` chỉ dùng dữ liệu có ngày `<= 7w + 6`.
**Không có `final_result`** trong bảng này. Khi chấm BR4, join với `fact_enrollment`.

| Cột | Kiểu | Định nghĩa | Kiểm |
|---|---|---|---|
| `id_student`, `code_module`, `code_presentation` | | Khóa, như `fact_enrollment` | |
| `week_no` | INT64 | FK → `dim_week` | |
| `clicks_week` | INT64 | `SUM(sum_click)` trong tuần, 0 nếu không có | |
| `clicks_cum` | INT64 | Lũy kế `clicks_week` từ tuần −4 đến tuần này | |
| `active_days_week` | INT64 | Số ngày có click trong tuần | |
| `sites_week` | INT64 | Số học liệu khác nhau được mở trong tuần | |
| `n_submitted_cum` | INT64 | Số bài đã nộp có `date_submitted <= 7w + 6` | |
| `n_late_cum` | INT64 | Số bài `is_late` đã nộp đến hết tuần (chỉ TMA) | |
| `avg_score_cum` | FLOAT64 | Điểm TB không trọng số của các bài có điểm, nộp đến hết tuần | |
| `n_tma_missed_cum` | INT64 | Số TMA `weight > 0` có `deadline <= 7w + 6` mà chưa có dòng nộp với `date_submitted <= 7w + 6` (banked tính là đã nộp). Thêm theo quyết định 4 | |
| `is_pre_start` | BOOL | `week_no < 0` | 130.372 |
| `is_week_inactive` | BOOL | `clicks_week = 0` | 715.918 |
| `is_enrolled` | BOOL | `date_unregistration IS NULL OR date_unregistration > 7w + 6` | 1.043.478 |

---

## 4. Đổi SQL từ CSV (DuckDB) sang kho (BigQuery)

| Tuần 1 đọc từ CSV | Tuần 2 đọc từ bảng | Đổi gì |
|---|---|---|
| `courses` | `dim_presentation` | `module_presentation_length` thành `length_days` |
| `assessments` | `dim_assessment` | `date` thành `deadline` (Exam đã được điền; cột gốc là `deadline_raw`) |
| `vle` | `dim_vle_site` | |
| `studentInfo` | `fact_enrollment` + `dim_student` | `imd_band` không còn NULL mà là `'Unknown'`; `age_band` ở `fact_enrollment` |
| `studentRegistration` | `fact_enrollment` | |
| `studentAssessment` | `fact_submission` | `is_banked` là BOOL: viết `NOT is_banked` thay vì `is_banked = 0` |
| `studentVle` | `fact_vle_daily` | **Đã gộp click trùng**: ít dòng hơn CSV, tổng click giữ nguyên |
| view `student_week` | `fact_student_week` | |

Khác biệt cú pháp hay gặp:

| DuckDB | BigQuery |
|---|---|
| `FROM fact_x` | `` FROM `oulad.fact_x` `` |
| `median(x)` | `APPROX_QUANTILES(x, 2)[OFFSET(1)]`, hoặc `PERCENTILE_CONT(x, 0.5) OVER (...)` |
| `quantile_cont(x, 0.25)` | `PERCENTILE_CONT(x, 0.25) OVER (...)` (nội suy tuyến tính, đúng như BR4, BR7 yêu cầu) |
| `CAST(FLOOR(date / 7) AS INTEGER)` | `CAST(FLOOR(date / 7) AS INT64)` (cả hai cần CAST vì `FLOOR` trả về số thực) |
| `SUM(is_late::INT)` | `COUNTIF(is_late)` |

---

## 5. Muốn đổi hợp đồng thì làm sao

1. Mở Pull Request sửa file này, ghi rõ đổi gì và vì sao.
2. Báo nhóm. Cần **cả 2 người còn lại** duyệt mới được merge.
3. TV1 sửa ETL, chạy lại, nạp lại kho; TV2, TV3 sửa SQL bị ảnh hưởng.

Sau Cổng B (18/10) không đổi hợp đồng nữa, trừ khi sửa lỗi.

---

## 6. Quyết định đã chốt

Chốt ngày 08/10/2026.

- [x] **Bộ tên 4 bảng fact** dùng cột đầu, cùng bộ tên với kế hoạch 3 tuần và tài liệu đặc tả BR.
  Gặp tên cũ trong sheet hay tài liệu khác thì đổi theo bảng này:

  | Tên chốt | Sheet Fact / Cờ (cũ) | Sheet Task2 (cũ) |
  |---|---|---|
  | `fact_vle_daily` | `fact_vle_daily` | `fact_vle_click` |
  | `fact_submission` | `fact_assessment_result` | `fact_submission` |
  | `fact_enrollment` | `fact_registration` | `fact_enrollment` |
  | `fact_student_week` | `fact_registration_week` | `fact_student_week` |

- [x] **`is_late` chỉ tính TMA**: 16.320 dòng, khớp đáp án BR1 (16,8%). Định nghĩa trong sheet Fact và Cờ
  (`is_banked = 0 AND date_submitted > deadline`, ra 49.323 dòng) **không dùng nữa**, vì ngày của CMA
  không phải hạn nộp thật.

- [x] **Quyết định 2, 3, 4 của tài liệu đặc tả: duyệt nguyên.**
  QĐ2: loại GGG khỏi BR3, dùng cờ có sẵn `has_weighted_tma`, `is_first_weighted_tma`; không thêm `is_first_tma`.
  QĐ3: như mục `is_late` ở trên.
  QĐ4: thêm `n_tma_missed_cum` vào `fact_student_week`. Bốn dấu hiệu và điểm nguy cơ tính lúc truy vấn, không lưu vào bảng.

- [x] **Quyết định 6: chưa thêm `prev_code_presentation`.** Cột này chỉ phục vụ BR8, và BR8 có thể bị cắt
  vào 15/10. Nếu giữ BR8 thì thêm vào `dim_presentation` sau, không đổi grain.

Quyết định 1 (ẩn ô dưới 30 SV) và 5 (BR6 chỉ xét IMD) không đụng tới hợp đồng này.
