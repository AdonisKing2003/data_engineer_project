# Benchmark star / 3NF / bảng rộng (việc 3.9)

Đo lúc 26/10/2026 18:23, chạy hết 6.4 phút. File này do `scripts/run_bench.py` tự sinh;
chạy lại `make bench` để cập nhật. Số liệu thô: `bench/results/benchmark.raw.csv`, trung vị:
`bench/results/benchmark.medians.csv`, biểu đồ: `bench/results/benchmark.html`.

## Cấu hình

| | |
|---|---|
| Máy | 16 CPU, 15 GB RAM (nhìn từ container), Spark 3.5.3, driver memory 3g |
| PostgreSQL | 16, container mặc định: `shared_buffers` 128MB, `work_mem` 4MB; chỉ có khóa chính theo grain ở mọi bố trí (bỏ chỉ mục tối ưu của optimization.md trước khi đo) |
| BigQuery | Sandbox, vùng US, giá on-demand; tắt cache kết quả; thời gian là thời gian job (bắt đầu → kết thúc) |
| Lặp | 5 lần mỗi ô, lấy trung vị; PostgreSQL `VACUUM ANALYZE` mọi bảng rồi chạy nóng 1 lần trước khi đo |
| Bố trí | Star: kho chính. 3NF: `fact_submission`, `fact_vle_daily` bỏ cột mã đợt và tuần, tra lại qua dimension bằng view. Bảng rộng: mỗi fact nối sẵn mọi thuộc tính dimension. Chi tiết: [layouts.md](layouts.md) |
| Không đo | BigQuery bảng rộng 5×: dataset khoảng 8 GB, cộng các dataset đang có thì vượt hạn mức 10 GB của Sandbox |

## Truy vấn

| Mã | BR | Nội dung |
|---|---|---|
| `br1_q07` | BR1 câu 7 | tỷ lệ nộp trễ TMA: fact_submission + dim_assessment |
| `br2_q09` | BR2 câu 9 | tỷ trọng click theo loại hoạt động: fact_vle_daily + dim_vle_site |
| `br4_q14` | BR4 câu 14 | danh sách nguy cơ tuần 4: fact_student_week nối với chính nó + fact_enrollment |
| `br6_q18` | BR6 câu 18 | khoảng cách IMD: fact_enrollment + dim_student |

Ba bố trí của cùng engine và quy mô cho kết quả **giống hệt nhau ở mọi ô**.

## Thời gian trung vị (giây)

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

## Bytes quét trên BigQuery (MB)

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

## Giải thích (viết tay, script giữ nguyên khi chạy lại)

Viết ngày 27/10/2026 theo số liệu của lần đo ở đầu file.

### Kích thước của từng bố trí

| Bảng lớn nhất | Star | 3NF | Bảng rộng |
|---|---:|---:|---:|
| PostgreSQL 1×: bảng click (`fact_vle_daily` / `_n` / `wide_vle_daily`) | 816 MB | 618 MB | 1.675 MB |
| PostgreSQL 5×: cùng bảng | 4.080 MB | 3.088 MB | 8.371 MB |
| PostgreSQL 5×: bảng SV-tuần | 860 MB | 860 MB | 1.531 MB |
| BigQuery 1×: cả dataset | ~0,66 GB | 0,48 GB | 1,61 GB |

3NF nhỏ nhất vì bỏ cột mã đợt và tuần khỏi hai fact lớn; bảng rộng gấp đôi star vì mỗi dòng click mang thêm
khoảng mười thuộc tính của sinh viên, học liệu, đợt.

### PostgreSQL (lưu theo dòng)

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

### BigQuery (lưu theo cột)

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

### Bài học về cách đo

Lần chạy đầu ngay sau khi dựng xong các bố trí 5× (khoảng 15 GB bảng mới) cho thời gian PostgreSQL cao gấp tới 7 lần
(BR2 star 1×: 4,03 s so với 0,55 s ở lần đo này). Kế hoạch truy vấn hai lần giống hệt nhau; nguyên nhân là autovacuum
đang xử lý các bảng mới và tranh đĩa với truy vấn. Script nay chạy `VACUUM ANALYZE` mọi bảng trước khi đo.
Ngay cả khi đó, ở 5× các bảng lớn hơn bộ nhớ đệm đẩy nhau ra khỏi cache, nên chênh lệch dưới khoảng 15% giữa hai ô
PostgreSQL 5× không nên coi là khác biệt thật.

### Kết luận

| Bố trí | Được | Mất | Hợp khi |
|---|---|---|---|
| Star | Không bao giờ chậm hơn nhiều so với hai bố trí kia; dễ viết SQL; là chuẩn của kho phân tích | Lặp mã đợt ở bảng fact | Mặc định cho kho phân tích, cả PostgreSQL lẫn BigQuery |
| 3NF | Nhỏ nhất (bảng click nhỏ hơn 24%) | Thêm phép nối ở mỗi truy vấn; trên BigQuery không quét ít hơn star | Hệ thống ghi/sửa dữ liệu (OLTP), không phải kho phân tích |
| Bảng rộng | Bỏ phép nối; nhanh hơn ở bảng nhỏ | Gấp đôi dung lượng; chậm nhất khi bảng lớn hơn bộ nhớ trên engine lưu theo dòng; đổi một thuộc tính phải sửa nhiều dòng | Bảng nhỏ phục vụ một trang dashboard cố định, trên engine lưu theo cột |

Nhóm giữ star làm kho chính. Tăng tốc cho từng trang app làm bằng phân vùng, gom cụm, chỉ mục và bảng tổng hợp sẵn
([optimization.md](optimization.md)) thay vì đổi cả bố trí.
