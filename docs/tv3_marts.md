# TV3 dashboard marts

Tài liệu này mô tả hai mart phục vụ dashboard TV3, hợp đồng truy vấn của Home và cách làm mới thủ công trên BigQuery.

## Mart và grain

| Bảng | Grain | Các cột |
|---|---|---|
| **tv3_br2_weekly_mart** | `code_module`, `code_presentation`, `week_no`, `activity_type` | 14 cột từ truy vấn BR2 đầy đủ, cộng `mart_created_at`: `code_module`, `code_presentation`, `week_no`, `week_start_day`, `week_end_day`, `activity_type`, `enrolled_students`, `offering_week_total_clicks`, `avg_clicks_per_enrolled_student`, `activity_type_total_clicks`, `activity_type_avg_clicks_per_enrolled_student`, `activity_type_click_share`, `avg_clicks_rank`, `total_clicks_rank`, `mart_created_at` |
| **tv3_br3_student_mart** | `code_module`, `code_presentation`, `id_student` | `code_module`, `code_presentation`, `id_student`, `clicks_before_deadline`, `score`, `n`, `rho`, `mart_created_at` |

BR2 dùng toàn bộ kết quả của `sql/bigquery/br2_vle_weekly.sql`, giữ 20 loại hoạt động và mẫu số là số sinh viên còn học vào cuối tuần, kể cả sinh viên không có click. Truy vấn raw BR3 trên DuckDB và BigQuery (`sql/br3_spearman.sql` và `sql/bigquery/br3_spearman.sql`) đều trả `id_student` cùng từng cặp điểm-click và thống kê `n`, `rho` theo kỳ, khớp grain nội bộ của mart. Các truy vấn dashboard BR3 chỉ chiếu các cột cần hiển thị và không trả `id_student`.

## Hợp đồng truy vấn của Home

| Query | Kết quả |
|---|---|
| `br2_offerings` | Hai cột `code_module`, `code_presentation`, mỗi kỳ một dòng. BigQuery đọc mart; DuckDB liệt kê kỳ từ `dim_presentation` Parquet. |
| `br2_dashboard` | Với kỳ được chọn, trả các cột biểu đồ `week_no`, `activity_type`, `activity_type_click_share`, `activity_type_total_clicks`, cùng `enrolled_students`, `avg_clicks_per_enrolled_student` và `activity_type_avg_clicks_per_enrolled_student` cho từng tuần. |
| `br2_tma_deadlines` | Với kỳ được chọn, trả một cột `week_no`, không trùng và tăng dần. TMA có `deadline IS NOT NULL` được nhóm theo `FLOOR(deadline / 7)`. |
| `br3_summary` | Một dòng mỗi `code_module`, `code_presentation`, gồm `n`, `rho`; không có mã sinh viên. |
| `br3_dashboard` | Cặp click-điểm và `n`, `rho` của đúng kỳ được chọn; không có mã sinh viên. |

BigQuery dùng `@code_module` rồi `@code_presentation`. DuckDB dùng hai dấu `?` theo đúng thứ tự đó. Query không lọc kỳ dùng không có tham số.

Theo hợp đồng ngày của kho, deadline âm biểu thị ngày trước khai giảng và không tự nó là giá trị sai; query chỉ loại deadline NULL. Kiểm tra Parquet hiện có 106 TMA, không có deadline NULL hoặc âm. Các tuần TMA của FFF 2014J là `3, 7, 13, 19, 28`.

Các truy vấn BigQuery `br2_offerings`, `br2_dashboard`, `br3_summary` và `br3_dashboard` đọc hai mart trong dataset đang cấu hình; `br2_tma_deadlines` đọc `dim_assessment`. Kho Parquet hiện chỉ lưu các bảng star, không có bản sao mart riêng. Vì vậy các truy vấn DuckDB tạo cùng kết quả dashboard từ các bảng Parquet star; phần BR2 chỉ dựng lưới tuần-hoạt động của kỳ đã chọn, còn BR3 tính lại cặp học viên và correlation cho kỳ đã chọn hoặc toàn bộ kỳ trong query tổng hợp.

Trang BR2 cho phép chọn tuần và mặc định tuần 0 khi tuần này có trong kết quả. Thẻ tóm tắt hiển thị cohort cuối tuần, click trung bình toàn tuần, `forumng` và `oucontent`. Cả hai backend dùng `enrolled_students` làm mẫu số, tính tại cuối tuần theo quy tắc đăng ký; cohort gồm cả sinh viên không click. Heatmap và xu hướng top 5 vẫn dùng toàn bộ các tuần, còn vạch hạn TMA lấy từ offering đang chọn.

## Làm mới BigQuery

Lệnh mặc định chỉ chạy dry-run và ước lượng bytes đọc cho cả hai truy vấn nguồn:

    python scripts/build_tv3_marts.py

Lệnh tường minh tương đương là `python scripts/build_tv3_marts.py --dry-run`. Để làm mới thủ công sau khi kiểm tra ước lượng, chạy `python scripts/build_tv3_marts.py --apply`.

Script đọc `GCP_PROJECT_ID`, `BQ_DATASET` và `BQ_LOCATION`; dataset mặc định là `oulad`, location mặc định là `US`. Có thể cung cấp các giá trị qua môi trường hoặc file `.env` cục bộ. Cần cài `google-cloud-bigquery` và cấu hình Google Application Default Credentials.

Trước khi áp dụng, script dry-run cả hai truy vấn nguồn. Khi có `--apply`, script chỉ chạy `CREATE OR REPLACE TABLE` cho `BQ_DATASET.tv3_br2_weekly_mart` và `BQ_DATASET.tv3_br3_student_mart`. Các bảng star nguồn chỉ được đọc. Chạy lại cùng lệnh sẽ thay thế toàn bộ từng mart bằng snapshot mới, không nối thêm dòng.

Log gồm ước lượng bytes trước khi áp dụng; thời điểm bắt đầu, thời điểm job và thời điểm kết thúc; thời gian chạy, bytes xử lý và bytes tính phí; timestamp nằm trong mart; row count; số grain duy nhất; số dòng metadata; và thống kê đọc phục vụ kiểm tra grain. Lệnh dry-run không thay đổi bảng.

Không chạy `--apply` trong môi trường chưa được phép ghi BigQuery. Việc tạo hoặc thay thế mart là thao tác có ghi dữ liệu; các bước dry-run và kiểm tra SQL cục bộ không cần quyền đó.
