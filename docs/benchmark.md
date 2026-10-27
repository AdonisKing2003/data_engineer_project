# Benchmark bố trí dữ liệu — task 3.9

## Mục tiêu và phạm vi

Benchmark so sánh bốn workload đại diện BR1/Q7, BR2/Q9, BR4/Q14 và BR6/Q18 trên PostgreSQL và BigQuery, ở quy mô 1×/5×, theo ba bố trí `star`, `3nf` (partial normalization) và `wide`.

| Phạm vi | Số tổ hợp |
|---|---:|
| Ma trận đầy đủ | 48 |
| Được đo | 44 |
| Loại khỏi lần đo | 4 |

Bốn ô bị loại là BigQuery × 5× × `wide` cho cả bốn workload. Theo cấu hình lần đo trước, thêm các dataset `wide` 5× vào dung lượng dữ liệu đã có sẽ vượt giới hạn lưu trữ 10 GB của Sandbox; lý do này được ghi trong matrix, manifest và biểu đồ. Runner phải hiển thị rõ cả 48 ô, trạng thái lựa chọn và lý do loại; thiếu bất kỳ ô nào trong 44 ô đã chọn là lỗi, không được coi là một lần benchmark hoàn tất.

Một ô được chạy một warm-up và năm lượt đo. Vì vậy giao thức benchmark gồm 264 lượt truy vấn (44 × 6), trong đó 44 warm-up không tính vào thống kê thời gian. Thứ tự các ô được xen kẽ theo từng vòng, seed mặc định `39`, và thứ tự thực tế được lưu trong manifest để tái lập.

## Workload và giới hạn diễn giải nghiệp vụ

| Workload | Câu hỏi | Nội dung benchmark |
|---|---|---|
| BR1 | Q7 | Tỷ lệ nộp trễ của TMA không phải bài chuyển điểm; báo cáo cả số lượng mẫu, số bài trễ và tỷ lệ. |
| BR2 | Q9 | Tổng click theo `activity_type`; trả loại học liệu có tổng cao nhất, tổng toàn cục và tỷ trọng. |
| BR4 | Q14 | Danh sách nguy cơ tuần 4 và precision/recall/baseline theo quy tắc tham chiếu trong `tests/test_student_week.py`. |
| BR6 | Q18 | Tỷ lệ đạt của BBB/DDD/FFF kỳ 2014J giữa hai nhóm IMD; loại withdrawal trước kỳ và ẩn ô có dưới 30 sinh viên riêng biệt. |

BR1/Q7 và BR4/Q14 là workload benchmark, chưa mặc nhiên là SQL sản xuất đã được TV2 nghiệm thu. BR4 dùng phân vị chính xác `PERCENTILE_CONT`; SQL TV2 dùng `APPROX_QUANTILES`, nên chưa được xem là tương đương nếu chưa đối chiếu sai số và hợp đồng kết quả. Báo cáo benchmark mô tả workload được đo, không thay thế phê duyệt nghiệp vụ.

Oracle 1× được kiểm tra theo kết quả tham chiếu đã có trong test/tài liệu: BR1 97.088 mẫu, 16.320 bài trễ, 16,8%; BR2 `oucontent`, 11.206.803 trên 39.605.099 click, 28,3%; BR4 27.250 lượt học, 3.958 được cảnh báo, 3.189 đúng, precision 80,6%, recall 26,9%, baseline 43,5%; BR6 nhóm IMD 0–10% có 615 sinh viên và đạt 41,1%, nhóm 90–100% có 436 và đạt 63,3%, chênh lệch 22,2 điểm phần trăm. Oracle được kiểm trên warm-up 1×. Với 5×, runner kiểm tra quy tắc nhân bản theo từng trường: các số đếm của dữ liệu nhân bản tăng theo hệ số 5, còn tỷ lệ giữ nguyên; không suy rộng quy tắc này cho mọi chỉ số.

Warm-up của tất cả tổ hợp cùng workload và quy mô phải có cùng số dòng và cùng hash kết quả chuẩn hóa. Mỗi lượt đo cũng phải giữ số dòng/hash ổn định trong tổ hợp và khớp warm-up tham chiếu. Hash không phụ thuộc thứ tự dòng, nhưng giữ nguyên dòng trùng; `NULL`, số nguyên và số thực được chuẩn hóa nhất quán. Sai oracle, thiếu/nhân đôi lượt, sai hash hoặc sai row count đều làm run thất bại và ngăn xuất median/biểu đồ chính thức.

## Ma trận, dữ liệu và preflight

SQL của từng tổ hợp nằm dưới `sql/bench/<engine>/<layout>/`. Runner không tạo, xóa hoặc sửa bảng. Trước khi đo, người vận hành phải chuẩn bị dữ liệu nguồn và target 1×/5× cho các layout được chọn; thiếu target, bảng hoặc workload oracle thì runner dừng và chỉ rõ điều kiện thiếu.

PostgreSQL phải theo chính sách chỉ có index khóa chính. Preflight kiểm tra index của các bảng đích và từ chối đo khi có index phụ; runner không tự xóa index. Runner chạy `ANALYZE` trước khi đo và lưu phiên bản PostgreSQL server/client, `shared_buffers`, `work_mem`, danh sách index, row count ước lượng sau `ANALYZE` và kích thước bảng. Với BigQuery, manifest lưu phiên bản client library, project/location và row count/bytes cùng thời điểm tạo/sửa từ metadata API; engine phía dịch vụ được Google quản lý nên API không cung cấp phiên bản triển khai cho từng job. Đây là snapshot metadata tại thời điểm preflight, không phải transaction snapshot đóng băng dữ liệu suốt 264 lượt; người vận hành cần bảo đảm các bảng nguồn không bị thay đổi trong khi đo.

BigQuery tắt result cache ở mọi lượt và kiểm tra `cache_hit` sau khi job hoàn thành; cache hit làm run thất bại. Trước khi thực thi, `estimate-bq` dry-run 20 truy vấn BigQuery được chọn. Báo cáo tổng bytes ước lượng cho sáu lượt mỗi truy vấn (warm-up + năm lượt đo). Đây là ước lượng bytes processed, không phải kết quả đo hoặc báo giá. `bytes_processed` và `bytes_billed` ghi riêng theo job.

Thời gian so sánh giữa engine là thời gian phía client tính từ lúc gửi truy vấn đến khi nhận đủ kết quả, sau khi kết nối/client đã sẵn sàng. BigQuery job time được ghi riêng; không dùng nó thay cho client time. Không so trực tiếp job time với client time. PostgreSQL hiện không có metric bytes-scanned tương đương trong adapter; để trống nếu không lấy được, không suy diễn từ kích thước bảng.

## Lệnh vận hành

Các lệnh sau không chạy benchmark đầy đủ:

```powershell
python scripts/benchmark_layouts.py matrix
python scripts/benchmark_layouts.py estimate-bq
```

`matrix` không kết nối database. `estimate-bq` cần credentials và các target BigQuery được chọn để dry-run. Dùng `--runs` để xem/thẩm tra cấu hình số lượt; mặc định cho một run là 5.

Chỉ chạy sau khi nhóm xác nhận M3 và người vận hành đã kiểm tra dữ liệu/target:

```powershell
python scripts/benchmark_layouts.py run --confirm-m3 --runs 5
```

Hoặc trong container:

```powershell
docker compose exec -e CONFIRM_M3=1 -T app make bench
```

`make bench` từ chối chạy nếu không có `CONFIRM_M3=1` và chuyển xác nhận tường minh sang `--confirm-m3`. Cờ này là xác nhận của người vận hành, không tự chứng minh checklist M3 đã được nhóm hoàn tất. `--runs` có thể cấu hình qua `RUNS` trên Makefile, nhưng giá trị nghiệm thu của task này là 5. Runner cũng giữ cổng kiểm tra bộ SQL câu hỏi Q1–Q20; có đủ file là điều kiện cần, không chứng minh nội dung đã được nhóm review.

**Trạng thái hiện tại:** chưa chạy phép đo chính thức trong task 3.9. Bộ câu hỏi trên checkout hiện thiếu nhiều file, gồm Q7 và Q14; nhóm cần hoàn thành/xác nhận M3, chuẩn bị đủ dữ liệu 1×/5× và đạt preflight trước khi chạy. Không dùng `--confirm-m3` thay cho xác nhận của nhóm.

## Kết quả và tính tái lập

Mỗi run ghi vào `bench/results/<run_id>/`:

- `manifest.json`: commit, hash SQL, cấu hình/phiên bản, snapshot, phạm vi 44/48, bốn ô loại và thứ tự thực thi.
- `raw.csv`: từng warm-up/lượt đo, thời gian client, job time/bytes/cache khi có, row count, hash, target và tên SQL.
- `correctness.json`: trạng thái oracle/parity, kiểm tra mỗi lượt và chẩn đoán.
- `medians.csv`: chỉ được tạo khi toàn bộ cổng correctness đạt; có median, min, max, IQR, số lượt và các cột tương thích `query`, `median_s`, `runs`.
- `chart.html`: biểu đồ độc lập của run đã thành công.

Run được đánh dấu `incomplete` và manifest được ghi xuống đĩa trước truy vấn đầu tiên. Raw được flush khi có lượt mới. Nếu truy vấn lỗi hoặc parity sai, trạng thái và chẩn đoán được giữ lại; không tạo median/biểu đồ thành công và không cập nhật `bench/results/latest_success.json`. Chỉ sau khi tất cả cổng đạt, manifest chuyển sang `success` và con trỏ latest-success trỏ tới run đó. Dashboard chỉ đọc run thành công qua con trỏ và manifest, không dò CSV rời hoặc thư mục lịch sử theo thời gian sửa.

## Số liệu lịch sử và cách diễn giải

Đợt đo cũ được giữ nguyên riêng tại [`bench/results/historical_2026-10-26/`](../bench/results/historical_2026-10-26/). Raw có 220 lượt, median có 44 tổ hợp; tính lại median/min/max đều khớp raw. Bộ này không lưu kết quả truy vấn hoặc hash theo từng lượt, vì vậy cột lịch sử `same_as_star` chỉ phản ánh DataFrame lượt cuối và không thay thế cổng correctness mới.

Số liệu lịch sử cho thấy BigQuery 5× star chậm hơn 3NF khoảng 2,48× ở BR2 và 4,52× ở BR4; do đó nhận định “star không bao giờ chậm hơn nhiều” đã bị loại bỏ. Ở 18/44 ô, khoảng `(max-min)/median` không quá 10%; trung vị tỷ lệ dao động là 21,6%. Kết quả nhỏ hơn mức dao động nên được mô tả là chưa phân biệt được bằng giao thức này. Giải thích dựa trên cache, join, song song hóa hoặc cách tạo bảng phải ghi là giả thuyết nếu không có metadata/thí nghiệm trực tiếp.

Số liệu lịch sử chỉ để tham khảo và không trộn vào run mới. Không có số đo task 3.9 mới nào được tạo trong giai đoạn chờ M3.
