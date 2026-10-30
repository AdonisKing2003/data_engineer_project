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

## Phụ lục: số liệu và phân tích lần đo 26/10/2026 (TV1)

Đây là bộ số liệu lịch sử ở mục trên, đo bằng `scripts/run_bench.py` (runner cũ). Giới hạn bằng chứng của bộ này đã ghi ở mục trên: không lưu hash từng lượt, `same_as_star` chỉ so lượt cuối. Các giải thích nguyên nhân dưới đây là giả thuyết khi không có kế hoạch truy vấn hoặc metadata đi kèm.

### Cấu hình

| | |
|---|---|
| Máy | 16 CPU, 15 GB RAM (nhìn từ container), Spark 3.5.3, driver memory 3g |
| PostgreSQL | 16, container mặc định: `shared_buffers` 128MB, `work_mem` 4MB; chỉ có khóa chính theo grain ở mọi bố trí (bỏ chỉ mục tối ưu của optimization.md trước khi đo) |
| BigQuery | Sandbox, vùng US, giá on-demand; tắt cache kết quả; thời gian là thời gian job (bắt đầu → kết thúc) |
| Lặp | 5 lần mỗi ô, lấy trung vị; PostgreSQL `VACUUM ANALYZE` mọi bảng rồi chạy nóng 1 lần trước khi đo |
| Bố trí | Star: kho chính. 3NF: `fact_submission`, `fact_vle_daily` bỏ cột mã đợt và tuần, tra lại qua dimension bằng view. Bảng rộng: mỗi fact nối sẵn mọi thuộc tính dimension. Chi tiết: [layouts.md](layouts.md) |
| Không đo | BigQuery bảng rộng 5×: dataset khoảng 8 GB, cộng các dataset đang có thì vượt hạn mức 10 GB của Sandbox |

### Thời gian trung vị (giây)

Trong ngoặc là tỷ lệ so với star cùng engine và quy mô (lớn hơn 1 là chậm hơn star).

| Truy vấn | Engine | Quy mô | Star | 3NF | Bảng rộng |
|---|---|---:|---:|---:|---:|
| BR1 câu 7 | PostgreSQL | 1× | 0.012 | 0.013 (1.08×) | 0.013 (1.05×) |
| BR1 câu 7 | PostgreSQL | 5× | 0.047 | 0.052 (1.12×) | 0.055 (1.18×) |
| BR1 câu 7 | BigQuery | 1× | 0.191 | 0.408 (2.14×) | 0.180 (0.94×) |
| BR1 câu 7 | BigQuery | 5× | 0.188 | 0.210 (1.12×) | — |
| BR2 câu 9 | PostgreSQL | 1× | 0.549 | 0.635 (1.16×) | 0.560 (1.02×) |
| BR2 câu 9 | PostgreSQL | 5× | 3.418 | 3.975 (1.16×) | 5.317 (1.56×) |
| BR2 câu 9 | BigQuery | 1× | 0.383 | 0.215 (0.56×) | 0.176 (0.46×) |
| BR2 câu 9 | BigQuery | 5× | 1.612 | 0.649 (0.40×) | — |
| BR4 câu 14 | PostgreSQL | 1× | 0.168 | 0.170 (1.01×) | 0.178 (1.06×) |
| BR4 câu 14 | PostgreSQL | 5× | 1.045 | 1.062 (1.02×) | 1.215 (1.16×) |
| BR4 câu 14 | BigQuery | 1× | 0.407 | 0.382 (0.94×) | 0.285 (0.70×) |
| BR4 câu 14 | BigQuery | 5× | 3.098 | 0.685 (0.22×) | — |
| BR6 câu 18 | PostgreSQL | 1× | 0.007 | 0.008 (1.01×) | 0.007 (0.89×) |
| BR6 câu 18 | PostgreSQL | 5× | 0.036 | 0.033 (0.91×) | 0.024 (0.67×) |
| BR6 câu 18 | BigQuery | 1× | 0.225 | 0.241 (1.07×) | 0.172 (0.76×) |
| BR6 câu 18 | BigQuery | 5× | 0.206 | 0.225 (1.09×) | — |

### Bytes quét trên BigQuery (MB)

Với BigQuery, tiền và hạn mức tính theo bytes quét nên đây là chỉ số chính.

| Truy vấn | Quy mô | Star | 3NF | Bảng rộng |
|---|---:|---:|---:|---:|
| BR1 câu 7 | 1× | 1.7 | 1.7 | 1.2 |
| BR1 câu 7 | 5× | 8.7 | 8.7 | — |
| BR2 câu 9 | 1× | 135.5 | 135.5 | 147.7 |
| BR2 câu 9 | 5× | 676.9 | 676.9 | — |
| BR4 câu 14 | 1× | 79.2 | 79.2 | 79.2 |
| BR4 câu 14 | 5× | 396.0 | 396.0 | — |
| BR6 câu 18 | 1× | 1.4 | 1.4 | 1.2 |
| BR6 câu 18 | 5× | 7.1 | 7.1 | — |

### Phân tích

#### Kích thước của từng bố trí

| Bảng lớn nhất | Star | 3NF | Bảng rộng |
|---|---:|---:|---:|
| PostgreSQL 1×: bảng click (`fact_vle_daily` / `_n` / `wide_vle_daily`) | 816 MB | 618 MB | 1.675 MB |
| PostgreSQL 5×: cùng bảng | 4.080 MB | 3.088 MB | 8.371 MB |
| PostgreSQL 5×: bảng SV-tuần | 860 MB | 860 MB | 1.531 MB |
| BigQuery 1×: cả dataset | ~0,66 GB | 0,48 GB | 1,61 GB |

3NF nhỏ nhất vì bỏ cột mã đợt và tuần khỏi hai fact lớn; bảng rộng gấp đôi star vì mỗi dòng click mang thêm
khoảng mười thuộc tính của sinh viên, học liệu, đợt.

#### PostgreSQL (lưu theo dòng)

- **Ở 1×, ba bố trí chênh nhau không quá 16%.** Toàn bộ dữ liệu vừa bộ nhớ; phép nối với dimension nhỏ (6.364 học
  liệu, 206 bài, 28.785 sinh viên) là hash join rẻ, nên bỏ phép nối (bảng rộng) hay thêm phép nối (3NF) đều không
  đáng kể.
- **Ở 5×, bảng rộng chậm nhất ở truy vấn quét bảng click (BR2: 5,32 s, gấp 1,56 lần star).** PostgreSQL lưu theo dòng
  nên quét bảng là đọc cả dòng, kể cả các cột thuộc tính truy vấn không dùng. `wide_vle_daily` 8,4 GB so với 4,1 GB
  của star: đọc gấp đôi số trang và không còn vừa bộ nhớ đệm của máy. Phép nối mà bảng rộng tiết kiệm được chỉ là
  nối với 6.364 dòng học liệu.
- **3NF chậm hơn star 8–16% ở BR1, BR2** dù bảng fact nhỏ hơn: view `fact_vle_daily`, `fact_submission` phải nối lại
  dimension để khôi phục mã đợt, và chi phí nối lớn hơn phần tiết kiệm khi đọc. Ở BR4, BR6 (không đụng hai fact
  chuẩn hóa) 3NF và star chạy trên cùng bảng nên thời gian như nhau.
- **Bảng rộng nhanh hơn ở truy vấn nhỏ có phép nối** (BR6 5×: 0,67 lần star): bỏ được nối `fact_enrollment` với
  `dim_student`, mà bảng `wide_enrollment` vẫn nhỏ.

#### BigQuery (lưu theo cột)

- **So bằng bytes quét, star và 3NF bằng nhau tới từng byte ở cả 4 truy vấn.** Truy vấn chỉ đọc các cột có ở cả hai
  bố trí (ví dụ BR2 chỉ đọc `id_site`, `sum_click`: 8.459.320 dòng × 2 cột × 8 byte, cộng `dim_vle_site`). Lưu theo
  cột nên các cột thừa của star không bị đọc, lợi thế "bảng nhỏ hơn" của 3NF biến mất.
- **Bảng rộng quét ít hơn ở BR1, BR6** (không phải đọc cột khóa để nối) nhưng **nhiều hơn 9% ở BR2**: đọc cột chuỗi
  `activity_type` lặp lại ở mọi dòng thay vì số nguyên `id_site` rồi nối với bảng học liệu nhỏ.
- **Thời gian ở 1× nằm trong khoảng 0,2–0,4 s cho mọi ô**, chủ yếu là chi phí khởi động job; chênh lệch giữa bố trí
  nhỏ hơn mức dao động giữa các lần chạy (ví dụ BR1 3NF 0,41 s là một ô dao động, bytes giống hệt star).
- **Ở 5×, star chậm hơn 3NF 2,5 lần (BR2) và 4,5 lần (BR4) dù đọc cùng bytes, cùng dữ liệu.** Đo thêm ngoài
  benchmark (8 lần chạy xen kẽ BR4): công tính toán gần bằng nhau (trung vị 10.173 so với 9.403 slot ms) nhưng thời
  gian chờ gấp 5 lần, tức bảng star 5× được đọc với ít luồng song song hơn. Khác biệt duy nhất là cách tạo bảng:
  `oulad_5x` được nạp bằng load job từ một file Parquet mỗi bảng (`etl/04_load_bq.py`), còn `oulad_3nf_5x` được tạo
  bằng `CREATE TABLE AS SELECT` chạy phân tán. Đây là giải thích hợp lý nhất nhưng chưa kiểm trực tiếp được, vì
  BigQuery không cho xem cách bảng được chia khối. Hệ quả: khi so bố trí trên BigQuery, các bảng nên được tạo cùng
  một cách; còn bytes quét là chỉ số so sánh đáng tin.

#### Bài học về cách đo

Lần chạy đầu ngay sau khi dựng xong các bố trí 5× (khoảng 15 GB bảng mới) cho thời gian PostgreSQL cao gấp tới 7 lần
(BR2 star 1×: 4,03 s so với 0,55 s ở lần đo này). Kế hoạch truy vấn hai lần giống hệt nhau; nguyên nhân là autovacuum
đang xử lý các bảng mới và tranh đĩa với truy vấn. Script nay chạy `VACUUM ANALYZE` mọi bảng trước khi đo.
Ngay cả khi đó, ở 5× các bảng lớn hơn bộ nhớ đệm đẩy nhau ra khỏi cache, nên chênh lệch dưới khoảng 15% giữa hai ô
PostgreSQL 5× không nên coi là khác biệt thật.

#### Kết luận

| Bố trí | Được | Mất | Hợp khi |
|---|---|---|---|
| Star | Trên PostgreSQL nhanh hơn 3NF 8–16% ở BR1, BR2 và không chậm hơn bảng rộng ở bảng lớn; trên BigQuery quét cùng bytes với 3NF; dễ viết SQL; là chuẩn của kho phân tích | Lặp mã đợt ở bảng fact; trên BigQuery 5× chậm hơn 3NF 2,5× (BR2) và 4,5× (BR4) về thời gian dù cùng bytes, nguyên nhân chưa kiểm được | Mặc định cho kho phân tích, cả PostgreSQL lẫn BigQuery |
| 3NF | Nhỏ nhất (bảng click nhỏ hơn 24%) | Thêm phép nối ở mỗi truy vấn; trên BigQuery không quét ít hơn star | Hệ thống ghi/sửa dữ liệu (OLTP), không phải kho phân tích |
| Bảng rộng | Bỏ phép nối; nhanh hơn ở bảng nhỏ | Gấp đôi dung lượng; chậm nhất khi bảng lớn hơn bộ nhớ trên engine lưu theo dòng; đổi một thuộc tính phải sửa nhiều dòng | Bảng nhỏ phục vụ một trang dashboard cố định, trên engine lưu theo cột |

Nhóm giữ star làm kho chính vì không có bố trí nào thắng ở mọi ô, và star dễ viết SQL nhất. Chỗ star chậm trên
BigQuery 5× cần lần đo của runner mới để xác nhận. Tăng tốc cho từng trang app làm bằng phân vùng, gom cụm, chỉ mục
và bảng tổng hợp sẵn ([optimization.md](optimization.md)) thay vì đổi cả bố trí.
