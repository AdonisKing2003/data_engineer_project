# BR3 — Click trước TMA đầu tiên và điểm

## Phạm vi và cách tính

- Mỗi nhóm là một cặp `code_module` và `code_presentation`.
- Chọn bài có `is_first_weighted_tma = TRUE` trong `dim_assessment`. Cờ này đã chốt quy tắc TMA có `weight > 0`, hạn sớm nhất và `id_assessment` nhỏ nhất nếu hòa.
- Mẫu gồm lượt nộp bài đó có `score IS NOT NULL` và `is_banked = FALSE`. Không lọc theo `final_result`, trạng thái rút học hay điểm đạt.
- Click là tổng `sum_click` của cùng sinh viên và kỳ học với `fact_vle_daily.date < dim_assessment.deadline`. Không đặt giới hạn dưới ngày; click trước khai giảng vẫn được tính theo đúng điều kiện của task. Click đúng ngày hạn không được tính.
- Sinh viên không có click trước hạn vẫn được giữ lại với `clicks_before_deadline = 0`.
- Tính Spearman bằng Pearson correlation trên thứ hạng trung bình (`average rank`) để xử lý giá trị click hoặc điểm bị trùng.
- Khoảng tin cậy 95% dùng Fisher z: `tanh(atanh(rho) ± 1.96 / sqrt(n - 3))`. Tính trên rho chưa làm tròn; bảng dưới hiển thị ba chữ số thập phân.
- `load_br3_data()` trong runner trả về bảng tóm tắt theo kỳ và các cặp click–điểm cho biểu đồ. Các cặp không chứa `id_student`.

## Kết quả trên warehouse hiện tại

Truy vấn trả về 19 kỳ với tổng cộng **21.693** cặp hợp lệ.

| Môn | Kỳ | n | Spearman rho | CI 95% dưới | CI 95% trên |
|---|---|---:|---:|---:|---:|
| AAA | 2013J | 358 | 0,369 | 0,276 | 0,455 |
| AAA | 2014J | 320 | 0,398 | 0,301 | 0,486 |
| BBB | 2013B | 1.338 | 0,287 | 0,237 | 0,335 |
| BBB | 2013J | 1.645 | 0,259 | 0,214 | 0,304 |
| BBB | 2014B | 1.149 | 0,247 | 0,192 | 0,301 |
| BBB | 2014J | 1.585 | 0,160 | 0,112 | 0,208 |
| CCC | 2014B | 935 | 0,316 | 0,257 | 0,373 |
| CCC | 2014J | 1.392 | 0,358 | 0,311 | 0,403 |
| DDD | 2013B | 971 | 0,317 | 0,259 | 0,372 |
| DDD | 2013J | 1.438 | 0,333 | 0,286 | 0,378 |
| DDD | 2014B | 897 | 0,328 | 0,268 | 0,385 |
| DDD | 2014J | 1.342 | 0,274 | 0,224 | 0,323 |
| EEE | 2013J | 825 | 0,328 | 0,266 | 0,388 |
| EEE | 2014B | 531 | 0,388 | 0,313 | 0,458 |
| EEE | 2014J | 911 | 0,406 | 0,350 | 0,458 |
| FFF | 2013B | 1.352 | 0,229 | 0,177 | 0,279 |
| FFF | 2013J | 1.806 | 0,226 | 0,182 | 0,269 |
| FFF | 2014B | 1.148 | 0,164 | 0,107 | 0,220 |
| FFF | 2014J | 1.750 | 0,273 | 0,229 | 0,316 |

Các mốc trong kế hoạch khớp sau khi làm tròn hai chữ số: AAA 2013J = 0,37; BBB 2014J = 0,16; EEE 2014J = 0,41.

## Chạy lại

```powershell
docker compose exec app python scripts/run_br3.py
```

SQL nằm tại `sql/br3_spearman.sql`. Hàm `load_br3_data()` trả về `(summaries, pairs)`; `pairs` có các cột môn, kỳ, `clicks_before_deadline`, `score`, không có mã sinh viên.

## BigQuery và câu hỏi Q12–Q13

`sql/bigquery/br3_spearman.sql` là bản BigQuery dùng cùng quy tắc tính như truy vấn DuckDB ở trên. Q12 kiểm tra số kỳ có TMA đầu tiên có trọng số và liệt kê các kỳ không có bài đó; Q13 tính lại hệ số cho AAA 2013J để đối chiếu mốc rho và `n` trong checklist.

Chạy từ thư mục gốc repo trong container `app` (BigQuery là engine mặc định của `run_sql.py`; dataset lấy từ `BQ_DATASET`, mặc định `oulad`):

```powershell
docker compose up -d app
docker compose exec -T app python scripts/run_sql.py sql/bigquery/br3_spearman.sql --engine bq
docker compose exec -T app python scripts/run_sql.py sql/questions/q12.sql --engine bq
docker compose exec -T app python scripts/run_sql.py sql/questions/q13.sql --engine bq
```

Q12 cần trả về 19 kỳ có TMA đầu tiên có trọng số và 3 kỳ không có, đều thuộc GGG. Q13 cần trả về `n = 358` và `rho` xấp xỉ `0.369` (làm tròn hai chữ số: `0.37`). Truy vấn BR3 chính trả về một dòng cho mỗi lượt nộp hợp lệ, kèm `n` và `rho` theo kỳ; khoảng tin cậy Fisher được tính ở Python, không phải trong SQL.

### Xác minh BigQuery ngày 19/10/2026

Đã chạy `sql/bigquery/br3_spearman.sql`, Q12 và Q13 trên dataset mặc định `oulad`. BR3 trả 21.693 dòng thuộc 19 kỳ; các mốc AAA 2013J (`n=358`, `rho=0.368810`), BBB 2014J (`n=1.585`, `rho=0.160`) và EEE 2014J (`n=911`, `rho=0.406`) khớp với DuckDB. BigQuery quét 308,9 MB cho truy vấn chi tiết BR3 và Q13; Q12 quét 0 MB theo metadata báo cáo.

Lệnh chạy:

```powershell
docker compose run --rm --no-deps app python scripts/run_sql.py sql/bigquery/br3_spearman.sql --engine bq
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q12.sql --engine bq
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q13.sql --engine bq
```

## Kiểm tra phạm vi

- Có 19 bài TMA đầu tiên có trọng số trong `dim_assessment`; sau khi loại bài banked và thiếu điểm còn 21.693 cặp.
- Có **186** cặp không có click trước hạn khi tính toàn bộ ngày thỏa `date < deadline`. Nếu thêm điều kiện `date >= 0`, số này thành 281 do 95 sinh viên chỉ có click trước khai giảng; điều kiện đó không có trong task và làm lệch mốc rho AAA 2013J, EEE 2014J.
- Xác nhận 12.117 cặp có click đúng ngày hạn, tổng 285.453 click; các click này bị loại bởi điều kiện nghiêm ngặt `date < deadline`.
- Đã kiểm tra công thức average rank trên nhóm có hai giá trị đồng hạng: cả hai nhận hạng trung bình 1,5.
- Kết quả được chạy trực tiếp trên Parquet hiện có bằng DuckDB 1.5.6.
