# Phần TV1: Kiến trúc, ETL, stream, kiểm thử và tối ưu

*Bản nháp ngày 26/10/2026, gửi TV3 ghép vào báo cáo chung. Số liệu lấy từ [etl_timing.md](etl_timing.md),
[optimization.md](optimization.md), [contract.md](contract.md) và kết quả `pytest` trên kho 1×.*

## 1. Kiến trúc

### 1.1 Thành phần

| Thành phần | Vai trò | Lý do chọn |
|---|---|---|
| Docker Compose (`app` + `postgres:16`) | Môi trường chạy giống nhau trên cả 3 máy (Linux, Windows) | Không cài tay Java, Spark, thư viện; một lệnh `docker compose up -d` là đủ |
| Apache Spark 3.5 (PySpark, chế độ local) | ETL batch và stream | `studentVle` có 10,6 triệu dòng; cùng một engine cho cả batch và Structured Streaming |
| Parquet (`data/warehouse/`) | Kho trung gian, nguồn chung cho mọi engine | Lưu theo cột, giữ kiểu dữ liệu; DuckDB đọc thẳng khi phát triển SQL |
| Google BigQuery (Sandbox) | Kho chính cho dashboard | Không quản trị máy chủ, tính theo bytes quét; Sandbox miễn phí (10 GB lưu trữ, 1 TB truy vấn/tháng) |
| PostgreSQL 16 | Kho đối chứng | So kết quả với BigQuery và làm nền cho benchmark star / 3NF / bảng rộng |
| DuckDB | Chạy SQL trên Parquet tại máy | Viết và kiểm SQL nhanh, không tốn hạn mức BigQuery |
| Streamlit | Dashboard | Viết bằng Python, đọc BigQuery hoặc DuckDB |

### 1.2 Luồng dữ liệu

```
7 file CSV OULAD (data/raw)
   │  01_staging      Spark đọc với schema khai báo sẵn, "?" và "" → NULL
   ▼
staging (Parquet, 7 bảng stg_*)
   │  02_clean_dims   5 dimension + fact_enrollment
   │  03_facts        fact_vle_daily, fact_submission
   │  06_student_week fact_student_week (ảnh chụp SV × tuần)
   ▼
kho star (Parquet, 9 bảng) ──► DuckDB (phát triển SQL, test)
   │  04_load_bq   ──► BigQuery dataset oulad      ──► Streamlit
   │  05_load_pg   ──► PostgreSQL schema public
   │  07_scale     ──► kho 5×: oulad_5x / schema x5 (benchmark)

Nhánh stream: studentVle chia theo ngày → phát lại vào thư mục → Spark Structured Streaming
              → cộng dồn click theo SV × tuần → so với fact_student_week của bản batch
```

### 1.3 Chạy lại từ đầu

Toàn bộ pipeline chạy bằng một lệnh `make all` trong container (`scripts/run_all.py`): staging → dims → facts →
bảng SV-tuần → BigQuery → PostgreSQL → pytest, dừng ngay ở bước lỗi đầu tiên và tự ghi thời gian từng bước ra
[etl_timing.md](etl_timing.md). README hướng dẫn từ lúc clone đến lúc mở app. Khóa Google Cloud và `.env` không
nằm trong repo; máy chưa có khóa vẫn chạy được bằng `make all-local` (bỏ bước BigQuery).

## 2. Mô hình kho

Thiết kế đầy đủ ở 3 mức ý niệm, luận lý, vật lý (sơ đồ thực thể, star schema, kiểu dữ liệu, kích thước và cách
lưu trên từng engine) ở [design_levels.md](design_levels.md). Các mô hình dữ liệu khác dùng trong project (3NF,
bảng rộng, dạng lồng, tài liệu JSONB, khóa-giá trị) và số đo so với bảng phẳng ở [data_models.md](data_models.md).
Mục này tóm tắt mức luận lý.

Kho theo mô hình chiều của Kimball, dạng constellation: 4 bảng fact dùng chung 5 dimension. Giữ khóa gốc của OULAD
(`id_student`, `id_assessment`, `id_site`, cặp `code_module` + `code_presentation`), không tạo khóa thay thế, để SQL
của nhóm và đáp án mẫu dùng chung được một bộ khóa. Tên bảng, cột, kiểu và định nghĩa từng cờ được chốt trong
[contract.md](contract.md) ngày 08/10, làm "hợp đồng" giữa người dựng kho và người viết SQL.

| Bảng | Grain (một dòng là) | Số dòng |
|---|---|---:|
| `dim_presentation` | một đợt học | 22 |
| `dim_student` | một sinh viên | 28.785 |
| `dim_assessment` | một bài kiểm tra | 206 |
| `dim_vle_site` | một học liệu VLE | 6.364 |
| `dim_week` | một tuần, từ −4 đến 38 | 43 |
| `fact_enrollment` | một lượt đăng ký (SV × đợt) | 32.593 |
| `fact_vle_daily` | SV × đợt × học liệu × ngày | 8.459.320 |
| `fact_submission` | một lần nộp (SV × bài) | 173.912 |
| `fact_student_week` | SV × đợt × tuần (ảnh chụp as-of) | 1.342.949 |

## 3. ETL và quy tắc làm sạch

### 3.1 Các bước và thời gian

Đo bằng `make all` trên máy 16 CPU, 8 GB RAM cấp cho container, Spark driver 3 GB.

| Bước | Nội dung | Thời gian (s) |
|---|---|---:|
| Staging | 7 CSV → Parquet | 46,0 |
| Dimension | làm sạch, 5 dimension + `fact_enrollment` | 38,4 |
| Fact | `fact_vle_daily` + `fact_submission` | 31,6 |
| Bảng SV-tuần | `fact_student_week` | 33,2 |
| Nạp BigQuery | 9 bảng | 83,5 |
| Nạp PostgreSQL | 9 bảng | 25,1 |
| Kiểm thử | pytest | 45,1 |
| **Tổng** | | **303,0** |

Bảng nặng nhất là `fact_vle_daily`: 10.655.280 dòng vào, 8.459.320 dòng ra, ghi Parquet 17,4 s, nạp BigQuery 30,0 s.

### 3.2 Nguyên tắc

- **Không xóa dòng, không sửa giá trị gốc.** Chỗ nào dữ liệu có vấn đề thì thêm cờ kiểu `BOOL` để người phân tích
  tự quyết định lọc hay giữ.
- **Ngày giữ dạng số nguyên** tính từ ngày khai giảng (âm là trước khai giảng), như dữ liệu gốc.
- **Tuần tính bằng `FLOOR(date / 7)`.** Phép chia nguyên `date // 7` của DuckDB và `DIV` của BigQuery làm tròn về 0,
  khiến ngày −1 rơi vào tuần 0 thay vì tuần −1. Cả ETL và hợp đồng đều chốt dùng `FLOOR`, có test riêng.
- **Mỗi bảng kiểm lại số dòng ngay sau khi ghi** và so với con số đã chốt trong hợp đồng.

### 3.3 Các vấn đề dữ liệu và cách xử lý

| Vấn đề trong dữ liệu gốc | Cách xử lý | Số dòng |
|---|---|---:|
| `studentVle` có nhiều dòng trùng khóa SV × học liệu × ngày | Gộp, cộng `sum_click`, ghi số dòng gốc vào `n_records`; tổng click giữ nguyên 39.605.099 | 10.655.280 → 8.459.320 |
| `imd_band` thiếu | Ghi `'Unknown'`, thêm cờ `imd_unknown` | 971 SV (1.111 lượt) |
| `imd_band` ghi `10-20` thay vì `10-20%` | Chuẩn hóa thành `10-20%` | |
| Bài Exam không có ngày hạn (`date` NULL) | `deadline = length_days` của đợt, giữ cột gốc `deadline_raw`, cờ `deadline_imputed` | 11 bài |
| `age_band` của một SV khác nhau giữa các đợt | Đặt `age_band` ở `fact_enrollment` thay vì `dim_student` | 72 SV |
| Thiếu ngày đăng ký | Giữ NULL, cờ `reg_date_missing` | 45 lượt |
| `final_result = Withdrawn` nhưng không có ngày rút, hoặc ngược lại | Giữ nguyên, cờ `result_inconsistent` | 102 lượt |
| Bài nộp không có điểm | Giữ NULL, cờ `score_missing` | 173 lượt nộp |
| Nộp sau khi đợt học đã kết thúc | Cờ `is_beyond_course` | 85 lượt nộp |
| Bài có trọng số 0 | Cờ `zero_weight` | 56 bài |
| Bài chuyển điểm từ đợt trước (`is_banked`) | Không tính trễ hạn, `days_late` để NULL | 1.909 lượt nộp |
| Định nghĩa "trễ hạn" trong tài liệu gốc tính cả CMA (49.323 lượt), nhưng ngày của CMA không phải hạn nộp thật | `is_late` chỉ tính TMA, khớp đáp án BR1 (16,8%) | 16.320 lượt nộp |

Các cờ khác dùng cho BR: `withdrawn_before_start` (3.097 lượt rút từ ngày 0 trở về trước), `no_vle_activity`
(3.365 lượt không có click nào), `is_first_weighted_tma` (19 bài, mỗi đợt có TMA tính điểm một bài), `is_repeat`
(4.172 lượt học lại).

### 3.4 Bảng SV-tuần và chống rò rỉ nhãn

`fact_student_week` là ảnh chụp theo tuần cho trang Cảnh báo (BR4) và trang Sinh viên (BR7). Mỗi lượt đăng ký có đủ
các tuần từ −4 đến tuần cuối của đợt, kể cả tuần không có click (ghi 0) và tuần sau khi đã rút (cột `is_enrolled`
cho biết còn học hay không). Các cột lũy kế (`clicks_cum`, `n_submitted_cum`, `avg_score_cum`, `n_tma_missed_cum`…)
tuân theo **quy tắc as-of**: cột của tuần `w` chỉ dùng dữ liệu có ngày ≤ `7w + 6`.

Bảng **không có cột `final_result`**. Nhãn kết quả cuối kỳ chỉ nằm ở `fact_enrollment` và chỉ được nối vào khi chấm
độ chính xác của danh sách nguy cơ. Test `test_br4_list_ignores_final_result` đổi `final_result` rồi tính lại danh sách
nguy cơ tuần 4 và kiểm danh sách không đổi. Test `test_no_label_column` kiểm bảng không có cột nhãn.

### 3.5 Nạp kho

- **BigQuery:** mỗi bảng nạp bằng một load job với `WRITE_TRUNCATE`. Một job thành công thì thay cả bảng, thất bại
  thì bảng cũ còn nguyên, không có trạng thái nạp dở. Sau khi nạp, so `num_rows` của bảng với số dòng Parquet.
- **PostgreSQL:** mỗi bảng một transaction (xóa bảng cũ, tạo bảng, `COPY`, thêm khóa chính rồi mới commit), sau đó
  `ANALYZE`. NULL được giữ
  là NULL khi đi qua CSV (có test riêng). Số dòng PostgreSQL bằng số dòng BigQuery ở cả 9 bảng.
- **Chạy lại không nhân đôi:** Spark ghi mọi bảng ở chế độ overwrite, BigQuery dùng `WRITE_TRUNCATE`, PostgreSQL tạo lại bảng
  trong cùng transaction. Có test nạp PostgreSQL hai lần liên tiếp.

### 3.6 Kho 5× cho benchmark

`make scale` chép mỗi sinh viên thành 5 bản: bản `i` có `id_student` = mã gốc + `i` × 10.000.000, kéo theo toàn bộ
dòng fact của sinh viên đó. Dimension tĩnh (đợt, bài, học liệu, tuần) giữ nguyên. Vì chép nguyên vẹn nên mọi tỷ lệ
(tỷ lệ trễ hạn, phân bố click theo đợt) bằng kho 1×, chỉ khối lượng tăng 5 lần: `fact_vle_daily` 42,3 triệu dòng
(2,6 GB trên BigQuery). Kho 5× nằm ở dataset `oulad_5x` và schema `x5`.

## 4. Xử lý stream

OULAD là dữ liệu lịch sử, không có luồng sự kiện thật. Nhóm không dùng Kafka mà **phát lại có kiểm soát**:
một script thả dần click theo từng ngày vào một thư mục, Spark Structured Streaming đọc thư mục đó. Cách này vẫn là
xử lý stream (micro-batch, trạng thái, ghi tăng dần) nhưng bớt một hệ thống phải cài đặt và vận hành.

| Bước | Script | Nội dung |
|---|---|---|
| Chia ngày | `stream/split_days.py` | Chia `studentVle` thành 295 file, mỗi file một ngày (ngày −25 đến 269) |
| Phát lại | `stream/replay.py` | Thả từng file theo thứ tự ngày. File được chép vào tên ẩn rồi đổi tên một lần, nên Spark không đọc phải file đang chép dở. Thả xong thì tạo file `_DONE` |
| Xử lý | `stream/stream_weekly.py` | `readStream` dạng file source, tối đa 7 file mỗi micro-batch (khoảng một tuần). Trạng thái là tổng click của từng SV × đợt × tuần. `outputMode("update")`: mỗi micro-batch chỉ ghi các dòng vừa đổi, kèm `batch_id` |
| Đối chiếu | `stream/compare.py` | Lấy giá trị mới nhất của mỗi dòng, cộng dồn ra `clicks_cum`, so với `fact_student_week` của bản batch |

Kết quả lần chạy gần nhất (`make stream`): 295 file, 44 micro-batch, 97,5 s.

| Chỉ số | Giá trị |
|---|---:|
| Số dòng SV × tuần đem so | 1.342.949 |
| Lệch `clicks_week` | 0 |
| Lệch `clicks_cum` | 0 |
| Tổng click bản batch / bản stream | 39.605.099 / 39.605.099 |
| Dòng có ở stream mà batch không có | 0 |
| Số dòng cập nhật stream đã ghi qua các micro-batch | 885.466 |

Bản stream chỉ sinh dòng cho tuần có click; tuần không có click được tính là 0 khi so với bản batch.

**Hạn chế:** dữ liệu gốc chỉ có ngày, không có giờ, nên thứ tự sự kiện trong một ngày không xác định được. Tốc độ
phát lại do người chạy chọn (`--delay`), không phản ánh tải thật.

## 5. Kiểm thử

`make test` chạy 174 test (169 test của TV1 và 5 test SQL của TV2), tất cả đều qua. Bảng nào chưa dựng thì test của
bảng đó tự bỏ qua.

| Nhóm kiểm tra | Nội dung | Số test |
|---|---|---:|
| Số dòng | Staging và 9 bảng kho đúng con số trong hợp đồng; PostgreSQL bằng Parquet | 25 |
| Cờ | Số dòng TRUE của từng cờ đúng hợp đồng, trên Parquet và PostgreSQL | 75 |
| Khóa | Khóa chính không trùng; không có khóa ngoại mồ côi | 19 |
| NULL | Tỷ lệ NULL từng cột đúng dự kiến; NULL giữ nguyên qua `COPY` | 10 |
| Đối soát tổng | Tổng `sum_click`, tổng điểm giữa nguồn và kho; tổng click của bảng SV-tuần | 4 |
| Quy tắc | Cột ngày là số nguyên; tuần tính bằng `FLOOR`; grain bảng SV-tuần đủ các tuần; cột lũy kế không giảm; `avg_score_cum` chỉ NULL khi chưa có điểm; bài TMA đầu tiên của BBB 2014J | 6 |
| Đáp án BR | Tỷ lệ trễ TMA 16,8% (BR1); danh sách nguy cơ BR4 (DDD 2014J tuần 4, mọi đợt); phân vị BR7 | 6 |
| Chống rò rỉ nhãn | Không có cột nhãn; đổi `final_result` không đổi danh sách BR4 | 2 |
| Chạy lại, stream | Nạp lại không nhân đôi; Spark ghi overwrite; stream khớp batch | 3 |
| Kho 5× | Số dòng gấp đúng 5; mỗi bản đủ 28.785 SV; tỷ lệ và phân bố click không đổi; đã nạp BigQuery và PostgreSQL | 19 |

Ngoài pytest, các câu hỏi mẫu trong `sql/questions/` chạy bằng `scripts/run_sql.py` trên cả BigQuery, PostgreSQL
và DuckDB để kiểm ba engine ra cùng đáp án.

## 6. Tối ưu truy vấn

Bốn ví dụ, đo bằng `make optimize` (`scripts/optimize.py`). Mỗi truy vấn chạy 5 lần, lấy trung vị; BigQuery tắt cache.
Mỗi ví dụ đều kiểm kết quả trước và sau tối ưu giống hệt nhau. Chi tiết, mã và kế hoạch truy vấn ở
[optimization.md](optimization.md).

| # | Kỹ thuật | Truy vấn của app | Chỉ số | Trước | Sau | Giảm |
|---|---|---|---|---:|---:|---:|
| 1 | Phân vùng `fact_student_week` theo `week_no` (BigQuery) | Danh sách nguy cơ BR4 tại tuần 4 | bytes quét | 79,2 MB | 4,7 MB | 16,8× |
| 2 | Gom cụm `fact_vle_daily` theo module, kỳ (BigQuery) | Click theo tuần × loại hoạt động của một đợt | bytes quét | 304,6 MB | 12,0 MB | 25,5× |
| 3 | Bảng tổng hợp sẵn cho app, mart BR2 (BigQuery) | Biểu đồ BR2 của một đợt | bytes quét | 381,6 MB | 1,2 MB | ~330× |
| 4 | Chỉ mục có `INCLUDE` trên `fact_vle_daily` (PostgreSQL) | Như ví dụ 2 | thời gian | ~390 ms | ~73 ms | ~5× |

Với BigQuery, chỉ số chính là bytes quét vì chi phí và hạn mức tính theo bytes. Thời gian ở cỡ dữ liệu dưới 1 GB chủ
yếu là chi phí khởi động job nên chênh lệch nhỏ. Ở ví dụ 4, thời gian dao động vài phần trăm giữa các lần chạy.

**Rút ra:**

- **Phân vùng chỉ có tác dụng khi truy vấn lọc cột phân vùng bằng hằng số.** Truy vấn BR4 ghép bảng với chính nó qua
  `p.week_no = w.week_no - 1`. Trên bảng đã phân vùng, bytes quét vẫn là 79,2 MB vì phía `p` đọc cả bảng. Chỉ khi
  thêm điều kiện `p.week_no = 3` (không đổi kết quả) thì bytes mới giảm còn 4,7 MB.
- **Gom cụm hợp với cột chuỗi hay được lọc** như mã module, mã kỳ: không cần cột kiểu ngày/số, không giới hạn số giá
  trị. Truy vấn một đợt chỉ đọc khoảng 1/25 bảng.
- **Bảng tổng hợp sẵn** đổi chi phí mỗi lần mở trang lấy chi phí dựng một lần, nhưng phải dựng lại sau mỗi lần nạp kho.
- **Chỉ mục PostgreSQL** phải bắt đầu bằng cột được lọc. Khóa chính có sẵn bắt đầu bằng `id_student` nên không giúp
  được truy vấn theo đợt. Kèm cột cần đọc (`INCLUDE`) cho phép quét chỉ trên chỉ mục, không mở bảng. Đổi lại, chỉ mục
  chiếm 499 MB (bảng 856 MB) và làm chậm lúc nạp.

## 7. Hạn chế

- BigQuery Sandbox tự xóa bảng sau 60 ngày và không cho dùng DML (`INSERT`, `UPDATE`), nên kho được nạp lại toàn bộ
  mỗi lần thay vì nạp tăng dần.
- Các tối ưu ở mục 6 được dựng thành bảng riêng (`opt_*`) để đo, chưa thay vào luồng nạp chính. Muốn dùng thật thì
  `04_load_bq.py` cần nạp thẳng vào bảng có phân vùng/gom cụm, và `05_load_pg.py` cần tạo chỉ mục sau khi nạp.
- Kho 5× là các bản sao, nên giữ nguyên phân bố nhưng không tạo thêm sự đa dạng thật của dữ liệu.
- Stream là phát lại dữ liệu lịch sử, không phải luồng thật (xem mục 4).
