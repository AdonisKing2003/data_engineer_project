# BR6 — Khoảng cách tỷ lệ đạt theo IMD

## Phạm vi và cách tính

- Nguồn: `fact_enrollment` nối `dim_student` theo `id_student`.
- Chỉ lấy BBB, DDD, FFF trong bốn kỳ 2013B, 2013J, 2014B, 2014J; loại enrollment có `withdrawn_before_start = TRUE` và chỉ giữ hai band `0-10%`, `90-100%`.
- Kết quả gộp ba môn thành một dòng cho mỗi kỳ. `code_module = 'BBB,DDD,FFF'` ghi rõ phạm vi gộp; `code_presentation` giữ mã kỳ.
- `n_students_*` đếm `id_student` duy nhất trong band và kỳ. `n_enrollments_*` đếm enrollment; một sinh viên học nhiều môn trong cùng kỳ có thể tạo nhiều enrollment.
- Tỷ lệ đạt = số enrollment có `final_result` là `Pass` hoặc `Distinction` / tổng enrollment đủ điều kiện trong band × 100. Tỷ lệ Distinction dùng số enrollment có `final_result = 'Distinction'` trên cùng mẫu số enrollment.
- `gap_pp` và `distinction_gap_pp` là trị tuyệt đối của chênh lệch hai tỷ lệ chưa làm tròn, làm tròn một chữ số thập phân và biểu diễn theo điểm phần trăm.
- Ngưỡng bảo vệ ô nhỏ dựa trên số sinh viên duy nhất. Khi `n_students < 30`, hai trường số đếm của band, các tỷ lệ của band và nhãn gap đều được ẩn; nhãn cỡ mẫu chỉ hiển thị `n < 30`. Gap đạt và gap Distinction cũng bị ẩn nếu một trong hai band dưới ngưỡng.

## Lược đồ đầu ra

Hai truy vấn DuckDB và BigQuery trả cùng 14 cột theo cùng thứ tự:

`code_module`, `code_presentation`, `n_students_imd_0_10`, `n_enrollments_imd_0_10`, `n_students_imd_0_10_label`, `rate_imd_0_10_pct`, `rate_distinction_imd_0_10_pct`, `n_students_imd_90_100`, `n_enrollments_imd_90_100`, `n_students_imd_90_100_label`, `rate_imd_90_100_pct`, `rate_distinction_imd_90_100_pct`, `gap_pp`, `distinction_gap_pp`.

## Kết quả trên warehouse Parquet hiện tại

| Kỳ | n SV 0–10% / enrollment | Đạt / Distinction 0–10% | n SV 90–100% / enrollment | Đạt / Distinction 90–100% | Gap đạt (điểm %) | Gap Distinction (điểm %) |
|---|---:|---:|---:|---:|---:|---:|
| 2013B | 466 / 468 | 31,2% / 4,7% | 322 / 322 | 56,5% / 13,4% | 25,3 | 8,7 |
| 2013J | 581 / 581 | 39,4% / 5,2% | 439 / 439 | 63,8% / 14,4% | 24,4 | 9,2 |
| 2014B | 410 / 411 | 39,2% / 4,4% | 282 / 282 | 62,1% / 15,6% | 22,9 | 11,2 |
| 2014J | 615 / 615 | 41,1% / 4,6% | 436 / 436 | 63,3% / 16,3% | 22,2 | 11,7 |

Số sinh viên duy nhất và số enrollment khác nhau vì các band được đếm theo sinh viên, còn tỷ lệ dùng kết quả theo enrollment. Mốc Q18 cho 2014J khớp: IMD 90–100% đạt 63,3%, IMD 0–10% đạt 41,1%, chênh lệch 22,2 điểm phần trăm.

## Chạy lại

Chạy truy vấn DuckDB trong thư mục repo:

```powershell
docker compose run --rm --no-deps app python scripts/run_br6.py
```

Truy vấn chính: [DuckDB](../sql/br6_imd_gap.sql) và [BigQuery](../sql/bigquery/br6_imd_gap.sql). Câu hỏi mẫu: [Q18](../sql/questions/q18.sql).

## Kiểm tra và giới hạn đối chiếu

- Đã chạy truy vấn DuckDB 1.5.6 trên Parquet hiện tại; kết quả có đủ bốn kỳ và khớp các mốc tỷ lệ trong checklist.
- Đã chạy `q18.sql` trên DuckDB với view đọc từ Parquet; kết quả là 41,1%, 63,3%, gap 22,2 điểm phần trăm.
- Đã kiểm tra ngưỡng bằng dữ liệu tổng hợp: nhóm 0–10% có 29 sinh viên duy nhất và 30 enrollment; cả hai số đếm, hai tỷ lệ và hai gap đều NULL, nhãn là `n < 30`. Nhóm có đúng 30 sinh viên vẫn hiển thị.
- Đã chạy `sql/bigquery/br6_imd_gap.sql` và Q18 trên BigQuery ngày 19/10/2026. BR6 trả cùng bốn dòng và cùng 14 cột như DuckDB; Q18 trả 41,1%, 63,3%, gap 22,2 điểm. BR6 quét 1,4 MB; Q18 quét 1,4 MB.

Lệnh BigQuery:

```powershell
docker compose run --rm --no-deps app python scripts/run_sql.py sql/bigquery/br6_imd_gap.sql --engine bq
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q18.sql --engine bq
```
