# BR2 — Click theo loại học liệu và tuần

## Phạm vi truy vấn chính

Truy vấn DuckDB tại `sql/br2_vle_weekly.sql` và bản BigQuery tại
`sql/bigquery/br2_vle_weekly.sql` có cùng phạm vi và tên cột đầu ra. Mỗi bản:

- Bao gồm tuần `0` đến `n_weeks - 1`, đủ 20 loại hoạt động; loại không có click trong tuần vẫn có dòng với số click bằng 0.
- Loại tuần trước khai giảng khỏi kết quả bằng `NOT is_pre_start`.
- Tính cohort còn học tại cuối tuần `w` theo `date_unregistration IS NULL OR date_unregistration > 7 * w + 6`.
- Dùng số sinh viên còn học cuối tuần làm mẫu số; gồm cả sinh viên không click trong tuần.
- Tính `offering_week_total_clicks`, trung bình click mỗi sinh viên, trung bình theo loại, tỷ trọng loại theo tuần, và hai hạng tuần trong từng môn/kỳ.
- Dùng `fact_vle_daily.sum_click` đã được ETL gộp ở grain sinh viên × học liệu × ngày.

## Câu hỏi mẫu Q9–Q11

Q9 và Q10 là câu hỏi toàn cục trong checklist, không phải phép tính theo một môn/kỳ hay theo cohort đang học cuối tuần. Q9 cộng mọi dòng `fact_vle_daily`, kể cả click trước khai giảng; mẫu số là tổng click toàn kho. Q10 cộng click của tất cả sinh viên và đợt theo `week_no` trong hợp đồng, gồm cả tuần âm trước khai giảng. Cả hai không dùng bộ lọc của truy vấn dashboard theo từng offering/tuần.

Q11 giới hạn ở FFF 2014J, tuần 0. Cột `is_enrolled` của `fact_student_week` áp dụng quy tắc hợp đồng tại cuối tuần, tức ngày 6; mẫu số giữ các sinh viên còn học không click, còn click chỉ được cộng cho cohort đó.

| Câu | Truy vấn | Phạm vi | Kết quả chuẩn |
|---|---|---|---|
| Q9 | `sql/questions/q09.sql` | Toàn kho, mọi ngày và đợt | `oucontent`: 11.206.803 / 39.605.099 click = 28,3% |
| Q10 | `sql/questions/q10.sql` | Toàn kho, mọi đợt; `week_no` theo hợp đồng | Tuần 2: 2.307.080 click |
| Q11 | `sql/questions/q11.sql` | FFF 2014J, tuần 0; cohort còn học cuối ngày 6 | 2.140 SV; 255.054 click; 119,2 click/SV |

Q9 và Q10 không được so với `activity_type_click_share` hay `total_clicks_rank` trong một dòng của BR2 dashboard: các cột đó được tính riêng trong từng môn/kỳ và tuần, trong đó tuần trước khai giảng bị loại. Q11 dùng đúng cohort cuối tuần của dashboard nhưng được truy vấn riêng theo đúng offering và tuần trong checklist.

Home mở sẵn tuần 0 khi offering có tuần này; bộ chọn tuần cập nhật các thẻ cỡ cohort, click trung bình toàn tuần, `forumng` và `oucontent`. Chỉ số trung bình đều dùng toàn bộ sinh viên còn học vào cuối tuần đã chọn, kể cả sinh viên không click. Oracle hồi quy cho FFF 2014J tuần 0 là 2.140 sinh viên, 119,2 click/sinh viên toàn tuần, 38,5 `forumng` click/sinh viên và 25,4 `oucontent` click/sinh viên. Đây là chỉ số của offering FFF 2014J và tuần 0; Q9/Q10 vẫn là câu hỏi toàn kho.

## Kết quả BR2 trên warehouse DuckDB

Truy vấn BR2 đầy đủ `sql/br2_vle_weekly.sql` trả về **16.340 dòng** trên toàn kho, bao phủ **22 kỳ** và **20 loại hoạt động**. Đây không phải số dòng của `br2_dashboard` trên Home: dashboard lọc theo offering đang chọn và chỉ trả về tuần-hoạt động của offering đó. Với FFF 2014J tuần 0, có **2.140 sinh viên**, **255.054 click**, trung bình **119,2 click/sinh viên**; `oucontent` có **54.354 click**, bằng **21,3%** click của tuần đó.

Trước thay đổi giao diện và query `br2_dashboard` ngày 20/10/2026, bốn regression test mới cho contract, kết quả FFF 2014J tuần 0 và bộ chọn tuần chạy với kết quả **4 failed** (exit code 1). Lỗi ghi nhận đúng các hành vi còn thiếu lúc đó: các cột cohort/average chưa có trong query và bộ chọn `br2_week` chưa tồn tại. Đây là bằng chứng RED trước triển khai; không phải kết quả kiểm tra hiện tại.

Dashboard xếp tuần riêng trong từng môn/kỳ. Với FFF 2014J, tuần có tổng click cao nhất là **tuần 0**, còn trung bình click/sinh viên cao nhất ở **tuần 34 (148,8)**. Q10 cộng tổng click giữa tất cả đợt trước khi xếp hạng nên trả về tuần 2.

## Chạy và xác minh

Các lệnh được chạy trong container từ thư mục gốc repo:

```powershell
docker compose run --rm --no-deps app python scripts/run_br2.py
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q09.sql --engine duckdb
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q10.sql --engine duckdb
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q11.sql --engine duckdb
```

Q9–Q11 mặc định chạy trên BigQuery nếu bỏ `--engine duckdb`:

```powershell
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q09.sql
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q10.sql
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q11.sql
docker compose run --rm --no-deps app python scripts/run_sql.py sql/bigquery/br2_vle_weekly.sql
```

SQL mẫu không ghi dataset/schema trước tên bảng theo quy ước của `scripts/run_sql.py`; runner chọn kho và dataset/schema. Bản BigQuery của BR2 ở `sql/bigquery/br2_vle_weekly.sql`; truy vấn DuckDB hiện có ở `sql/br2_vle_weekly.sql`.

### Bằng chứng chạy ngày 19/10/2026

Các truy vấn Q9–Q11 chạy thành công trên DuckDB và BigQuery. Kết quả BigQuery:

- Q9: `oucontent`, 11.206.803 click trên tổng 39.605.099, tỷ trọng 28,3% (237,0 MB quét).
- Q10: tuần 2, 2.307.080 click (135,3 MB quét).
- Q11: 2.140 sinh viên, 255.054 click, trung bình 119,184112 click/sinh viên (38,9 MB quét).
- Bản BR2 BigQuery chạy thành công, trả về 16.340 dòng và 14 cột (381,6 MB quét). Runner DuckDB `scripts/run_br2.py` cũng trả 16.340 dòng, 22 kỳ và 20 loại hoạt động.
