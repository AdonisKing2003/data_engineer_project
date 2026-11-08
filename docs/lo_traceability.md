# Chuẩn đầu ra → bằng chứng trong project

Mỗi chuẩn đầu ra của môn có ít nhất một tài liệu, một phần code và một con số đo được làm bằng chứng. Mọi con số
dưới đây chạy lại được bằng lệnh `make` ghi kèm, và phần lớn có test giữ cho nó đúng.

Theo đề cương, chuẩn 1.1 và 1.2 chấm qua tiểu luận và bài thi. Chuẩn 2.1 đến 3.2 chấm thêm qua thuyết trình, nên
mục cuối gợi ý slide và trang demo cho từng chuẩn.

## Tóm tắt

| Chuẩn đầu ra | Bằng chứng chính | Con số tiêu biểu |
|---|---|---|
| 1.1 Thiết kế CSDL ở mức ý niệm, luận lý, vật lý | [design_levels.md](design_levels.md), [contract.md](contract.md) | 8 thực thể → 5 dimension + 4 fact; 11 phụ thuộc hàm kiểm trên dữ liệu; cùng bảng click 42 MB / 516 MB / 816 MB trên Parquet / BigQuery / PostgreSQL |
| 1.2 Mô hình hóa từ quan hệ đến phi quan hệ | [data_models.md](data_models.md), [benchmark.md](benchmark.md) | 7 mô hình; bảng lồng quét ít hơn 33% nhưng tốn công tính toán gấp 14,4×; JSONB nhỏ hơn 7,4× nhưng chậm 2,9× ở câu hỏi cắt ngang |
| 2.1 Kiến trúc quản lý dữ liệu từ nhiều nguồn | [report_tv1.md](report_tv1.md) mục 1, 3 | 7 nguồn CSV, 4 tầng, 3 nơi lưu, 2 đường nạp batch và stream; `make all` 303 s |
| 2.2 Thiết kế kho dữ liệu | [design_levels.md](design_levels.md) mục 2, [benchmark.md](benchmark.md) | Constellation 4 fact; bảng ảnh chụp SV-tuần 1.342.949 dòng; star / 3NF / bảng rộng ở 1× và 5× |
| 3.1 Quản lý dữ liệu phức tạp | [report_tv1.md](report_tv1.md) mục 3, 5 | 3.810.465 dòng click trùng được gộp; 289 test; đảo nhãn không đổi danh sách cảnh báo 3.958 SV |
| 3.2 Xử lý dữ liệu theo kiểu mẫu hiện đại | [report_tv1.md](report_tv1.md) mục 4, 6, [optimization.md](optimization.md) | Stream từ Kafka có watermark khớp batch 0 lệch trên 1.342.949 dòng, trạng thái lúc lớn nhất nhỏ hơn ~10× so với không có watermark; tối ưu giảm 5,3× đến 330× |

---

## 1.1 Thiết kế CSDL ở mức ý niệm, luận lý, vật lý

| Mức | Bằng chứng | Ở đâu |
|---|---|---|
| Ý niệm | Sơ đồ thực thể nghiệp vụ: Học phần, Đợt học, Sinh viên, Bài kiểm tra, Học liệu, Đăng ký, Lần nộp, Lượt truy cập. Quy tắc nghiệp vụ rút ra ở mức này, như "nhóm tuổi thuộc về lượt đăng ký, không thuộc về sinh viên" (72 SV đổi nhóm tuổi) | [design_levels.md](design_levels.md) mục 1 |
| Luận lý | Star schema dạng constellation: 5 dimension, 4 fact, grain và khóa từng bảng; các quyết định (giữ khóa gốc, cờ thay vì xóa dòng, bảng SV-tuần không chứa nhãn) | [design_levels.md](design_levels.md) mục 2, [contract.md](contract.md) |
| Chuẩn hóa | Phụ thuộc hàm kiểm trên dữ liệu thật: `studentVle` chưa đạt 1NF (dòng trùng khóa), `studentInfo` vi phạm 2NF (`id_student` → thuộc tính SV). Tách theo phụ thuộc hàm ra bố trí 3NF, rồi phi chuẩn hóa có chủ đích ra star | [design_levels.md](design_levels.md) mục 2.4, `tests/test_staging.py` (11 test) |
| Vật lý | Ánh xạ kiểu dữ liệu trên 3 engine; kích thước từng bảng; khóa chính, phân vùng, gom cụm, chỉ mục B+-tree, `CLUSTER` theo chỉ mục | [design_levels.md](design_levels.md) mục 3, [optimization.md](optimization.md), [indexing.md](indexing.md) |
| Truy vết 3 mức | Một bảng nối thực thể ý niệm → bảng luận lý → cách lưu vật lý | [design_levels.md](design_levels.md) mục 4 |

Code: `etl/02_clean_dims.py`, `etl/03_facts.py` (mức luận lý thành bảng), `etl/04_load_bq.py`, `etl/05_load_pg.py`
(mức vật lý). Test khóa chính, khóa ngoại: `tests/test_warehouse.py`, `tests/test_postgres.py`.

## 1.2 Mô hình hóa từ quan hệ đến phi quan hệ

| Mô hình | Hiện thực trong project | Số đo |
|---|---|---|
| Quan hệ 3NF | PostgreSQL `three_nf`, BigQuery `oulad_3nf` (TV3) | Bảng click nhỏ hơn star 24%; trên PostgreSQL ngang star (chênh không quá 11%) |
| Mô hình chiều (star) | Kho chính BigQuery `oulad`, PostgreSQL `public` | Mốc so sánh |
| Bảng rộng phi chuẩn hóa | PostgreSQL `wide`, BigQuery `oulad_wide` (TV3) | Gấp đôi dung lượng; trên PostgreSQL 5× chậm hơn star ở truy vấn đọc fact lớn (BR1 2,02×, BR2 1,16×), nhanh hơn ở BR6 (0,61×) |
| Lưu trữ theo cột | Parquet, BigQuery | BigQuery chỉ quét cột cần: star và 3NF quét đúng cùng số bytes |
| Dạng lồng | BigQuery `nested_student_timeline` (`ARRAY<STRUCT>`) | 97,7 MB so với 123,9 MB bảng phẳng; BR4 quét 53,0 MB so với 79,2 MB, nhưng slot ms tăng 14,4× |
| Tài liệu | PostgreSQL `doc.student_timeline` (JSONB) | 33,3 MB so với 247,3 MB; câu hỏi cắt ngang chậm 2,9× |
| Khóa-giá trị | State store của Spark Structured Streaming (khóa SV × đợt × tuần) | Không watermark: 627.031 khóa giữ tới cuối. Có watermark (nguồn Kafka): lớn nhất 65.274 khóa, cuối còn 4.803 |

Kết luận của nhóm: chọn mô hình theo cách truy cập. Câu hỏi tổng hợp cắt ngang (6/8 yêu cầu nghiệp vụ) dùng star
lưu theo cột. Hồ sơ trọn vẹn một sinh viên hợp với tài liệu hoặc dạng lồng. Cập nhật theo khóa hợp với khóa-giá trị.
Mô hình đồ thị không dùng vì không câu hỏi nào cần duyệt quan hệ nhiều bước.

Chạy lại: `make models` (dạng lồng, tài liệu), `make bench` (3NF / star / bảng rộng, runner mới của TV3). Số liệu 3NF / star / bảng rộng ở bảng trên là của lần đo chính thức 07/11/2026 (`bench/results/20261107T165028Z_55925b1a/`).

## 2.1 Kiến trúc quản lý dữ liệu từ nhiều nguồn

| Thành phần kiến trúc | Bằng chứng |
|---|---|
| Nhiều nguồn có khóa và quy tắc khác nhau | 7 CSV: khóa ghép ở `studentInfo`, không có khóa ở `studentVle`, `"?"` là thiếu ở `imd_band`, ngày tương đối từ khai giảng ([report_tv1.md](report_tv1.md) mục 3.3) |
| Phân tầng | raw (CSV) → staging (Parquet, đặt kiểu) → kho (star) → phục vụ (BigQuery, mart cho app) ([report_tv1.md](report_tv1.md) mục 1.2) |
| Nhiều nơi lưu, mỗi nơi một vai trò | BigQuery là kho chính, PostgreSQL là kho đối chứng, Parquet + DuckDB để chạy tại máy |
| Hai đường nạp | Batch bằng Spark; stream bằng Spark Structured Streaming đọc click phát lại theo ngày, từ thư mục hoặc từ Kafka |
| Tách bên gửi khỏi bên xử lý | Kafka topic `oulad.clicks`, 4 partition, key `id_student`; Spark đọc theo offset, lưu offset vào checkpoint nên dừng rồi chạy lại vẫn đọc tiếp đúng chỗ ([report_tv1.md](report_tv1.md) mục 4.2) |
| Đối soát giữa các nơi lưu | Số dòng khớp ở mọi bảng; 20 câu hỏi mẫu viết bằng SQL chung, ra cùng đáp án trên BigQuery, PostgreSQL, DuckDB |
| Tầng phục vụ tách khỏi nơi lưu | App đọc qua `app/data.py`, đổi BigQuery / DuckDB bằng một biến môi trường `DATA_BACKEND` |
| Nhánh stream đi trọn tới người dùng | Producer → Kafka → Spark → BigQuery (bảng log ghi thêm + view lấy bản mới nhất, vì Sandbox cấm DML) → trang Click thời gian thực. View trên BigQuery khớp bản Parquet: 627.031 dòng, 39.605.099 click ([report_tv1.md](report_tv1.md) mục 4.3) |
| Chạy lại được ở mọi máy | Docker Compose; `make all` dựng lại toàn bộ trong 303 s ([etl_timing.md](etl_timing.md)) |
| Điều phối | DAG Airflow `oulad_batch`: chờ đủ 7 CSV → staging → dims → facts → SV-tuần → kiểm chất lượng trên Parquet → nạp BigQuery và PostgreSQL song song → toàn bộ test. Lập lịch hằng ngày, tự chạy lại khi lỗi ([report_tv1.md](report_tv1.md) mục 1.4) |

## 2.2 Thiết kế kho dữ liệu

| Khía cạnh | Bằng chứng |
|---|---|
| Mô hình chiều | Constellation: 4 fact (`fact_enrollment`, `fact_submission`, `fact_vle_daily`, `fact_student_week`) chia chung 5 dimension ([design_levels.md](design_levels.md) mục 2.2) |
| Grain rõ ràng | Mỗi fact ghi grain và có test khóa chính không trùng |
| Bảng ảnh chụp theo thời gian | `fact_student_week` (1.342.949 dòng): tuần `w` chỉ dùng dữ liệu tới hết tuần `w`, không chứa `final_result` |
| Chất lượng dữ liệu trong kho | Cờ `BOOL` thay vì xóa dòng (`deadline_imputed`, `is_late`, `result_inconsistent`...), số dòng TRUE của từng cờ có trong hợp đồng và được test |
| Tổng hợp sẵn cho app | Mart BR2, BR3 trên BigQuery ([tv3_marts.md](tv3_marts.md)); mart BR2 giảm bytes quét 330× ([optimization.md](optimization.md) ví dụ 3) |
| So sánh thiết kế | Star / 3NF / bảng rộng, 2 engine, 1× và 5×, 5 lần chạy mỗi ô ([benchmark.md](benchmark.md)). Không bố trí nào thắng ở mọi ô: trên BigQuery 5× star chậm hơn 3NF 2,5–4,5× về thời gian dù quét cùng bytes. Nhóm giữ star vì dễ viết SQL nhất và trên PostgreSQL nhanh hơn 3NF |
| Mở rộng quy mô | Kho 5× (`make scale`): mọi tỷ lệ giữ nguyên, nên dùng để kiểm SQL benchmark ra đúng |

## 3.1 Quản lý dữ liệu phức tạp

| Vấn đề | Cách xử lý | Bằng chứng |
|---|---|---|
| Dòng click trùng khóa | Gộp, cộng `sum_click`, ghi `n_records`: 10.655.280 → 8.459.320 dòng, tổng click giữ nguyên 39.605.099 | `tests/test_staging.py`, `tests/test_warehouse.py` |
| Giá trị thiếu, sai định dạng | `"?"` thành NULL; `imd_band` thiếu thành `'Unknown'` kèm cờ; `10-20` thành `10-20%` | [report_tv1.md](report_tv1.md) mục 3.3 |
| Hạn nộp thiếu | 11 bài thi lấy hạn = độ dài đợt, cờ `deadline_imputed` | [contract.md](contract.md) |
| Dữ liệu mâu thuẫn | 102 lượt có `final_result` và ngày rút không khớp: giữ lại, đánh cờ `result_inconsistent` | [contract.md](contract.md) |
| Rò rỉ nhãn | Bảng SV-tuần không có nhãn; test đảo toàn bộ `final_result` rồi chạy lại câu 14: danh sách 3.958 SV giữ nguyên, chỉ độ chính xác đổi | `tests/test_questions.py`, `tests/test_student_week.py` |
| Chạy lại không nhân đôi | Mọi bước ghi đè; test nạp hai lần vẫn đúng số dòng | `tests/test_pipeline.py` |
| Đúng trên nhiều engine | Cùng bộ số kiểm trên Parquet và PostgreSQL; 20 đáp án mẫu kiểm trên DuckDB | `tests/test_postgres.py`, `tests/test_questions.py` |
| Kiểm thử tổng | 289 test: kho, phụ thuộc hàm, SQL nghiệp vụ, đáp án mẫu, app, mart, benchmark | `make test` |

## 3.2 Xử lý dữ liệu theo kiểu mẫu hiện đại

| Kiểu mẫu | Bằng chứng |
|---|---|
| Xử lý phân tán | Spark 3.5 cho toàn bộ ETL batch và sinh kho 5× |
| Stream, nguồn thư mục | Spark Structured Streaming, micro-batch, có trạng thái, `outputMode("update")`: 295 file ngày, 44 micro-batch, 97,5 s; so với batch lệch 0 trên 1.342.949 dòng ([report_tv1.md](report_tv1.md) mục 4.1) |
| Stream, nguồn Kafka | Kafka làm hàng đợi sự kiện; cửa sổ 7 ngày theo thời gian sự kiện, watermark 7 ngày: 10.655.280 message, 63 micro-batch, 130,3 s, 0 dòng bị watermark bỏ, lệch 0 so với batch; trạng thái lớn nhất 65.274 khóa so với 627.031 khi không có watermark. Không trùng, không mất nhờ producer idempotent + checkpoint + ghi đè theo `batch_id` ([report_tv1.md](report_tv1.md) mục 4.2) |
| Kho dữ liệu đám mây không máy chủ | BigQuery, tính tiền theo bytes quét |
| Lưu trữ theo cột | Parquet, BigQuery; DuckDB chạy SQL thẳng trên Parquet |
| Tối ưu có số đo, áp dụng cho kho chính | Phân vùng 16,8×, gom cụm 15,9×, bảng tổng hợp sẵn 330× (bytes quét BigQuery); chỉ mục 5,3× (thời gian PostgreSQL). Đặt ngay khi nạp (`etl/04_load_bq.py`, `etl/05_load_pg.py`); mart dựng lại trong DAG ([optimization.md](optimization.md)) |
| Chỉ mục và hiệu năng truy vấn (bài 3 của môn) | Bảng `fact_student_week` đo 3 mức trên cùng câu hỏi "tuần 4 ai nguy cơ": BigQuery bảng thường / phân vùng / phân vùng + gom cụm (79,2 → 4,7 → 4,7 MB); PostgreSQL khóa chính / + chỉ mục B+-tree / + `CLUSTER` (125 → 172 → 74 ms; 22.016 → 22.047 → 567 trang). Chỉ mục một mình chậm hơn vì dòng nằm rải: minh họa clustering index. Chi phí ghi +91% ([indexing.md](indexing.md)) |
| Container, chạy một lệnh | Docker Compose; Makefile; `scripts/run_all.py` dừng ở bước lỗi đầu tiên và ghi thời gian từng bước. `requirements.lock` khóa đủ 70 gói, build lại ở đâu cũng ra cùng một bộ thư viện |
| Điều phối pipeline | Airflow 2.10 (`LocalExecutor`, CSDL trên PostgreSQL): sensor chờ dữ liệu nguồn, cổng chất lượng trước khi nạp, 2 bước nạp chạy song song, retries, báo lỗi qua log và webhook khi task lỗi hẳn; mỗi task gọi đúng một mục Makefile nên logic ETL không đổi ([report_tv1.md](report_tv1.md) mục 1.4) |
| Phục vụ người dùng | Dashboard Streamlit chia theo vai trò, đọc BigQuery; test khói `tests/test_app.py`. Trang Click thời gian thực tự tải lại mỗi 10 giây khi bật (mặc định tắt vì mỗi lần quét ~48 MB), độ trễ cỡ 5–10 s do mỗi load job BigQuery mất khoảng 5 s |

---

## Hạn chế cần nói trước khi bị hỏi

| Hạn chế | Ảnh hưởng tới chuẩn | Cách trả lời |
|---|---|---|
| Stream là phát lại dữ liệu lịch sử, không phải luồng thật; nguồn chỉ có ngày, không có giờ | 3.2 | Nguồn là Kafka, xử lý theo thời gian sự kiện có watermark, đúng như với luồng thật; chỉ phần gửi là phát lại. Lệnh `--late` minh họa dữ liệu đến trễ bị bỏ |
| Kafka chạy 1 broker, không có bản sao | 3.2 | Đủ để minh họa; production cần ít nhất 3 broker, replication factor 3 |
| Dashboard chậm hơn stream 5–10 s, bảng log trên BigQuery chỉ dài thêm | 2.1, 3.2 | Sandbox chỉ cho load job. Có billing thì dùng Storage Write API cho độ trễ dưới 1 s, và gộp log định kỳ bằng `MERGE` ([report_tv1.md](report_tv1.md) mục 4.3, 4.4) |
| 7 nguồn đều thuộc một bộ dữ liệu | 2.1 | Các file có khóa, chất lượng và quy tắc ngày khác nhau, nên vẫn phải hợp nhất như nhiều nguồn |
| BigQuery Sandbox: bảng tự xóa sau 60 ngày, không cho `INSERT`/`UPDATE` | 2.1, 3.2 | Kho batch nạp lại toàn bộ mỗi lần. Nhánh stream đã nạp tăng dần bằng load job ghi thêm + view lấy bản mới nhất, cùng cách dùng được cho kho batch |
| Chưa có CDC | 2.1 | Nguồn là file tĩnh, không có CSDL đang thay đổi; Sandbox cấm `MERGE`. Kiến trúc nếu làm (Debezium → Kafka → Spark → bảng staging → `MERGE`) và phần đã có sẵn ở [report_tv1.md](report_tv1.md) mục 8.2 |
| Bảng rộng 5× không dựng được trên BigQuery vì vượt hạn mức 10 GB | 1.2, 2.2 | So bảng rộng ở 1× trên BigQuery và ở 5× trên PostgreSQL |
| Star 5× trên BigQuery chậm hơn 3NF dù quét cùng bytes; giả thuyết là do cách tạo bảng, chưa kiểm được | 2.2 | So bằng bytes quét, chỉ số đáng tin trên BigQuery ([benchmark.md](benchmark.md)) |
| Kho 5× là bản sao, không thêm đa dạng thật | 2.2 | Dùng để đo tải, không dùng để rút kết luận nghiệp vụ |

## Gợi ý thuyết trình (chuẩn 2.1 đến 3.2)

| Chuẩn | Slide nên có | Một con số để nói | Trang demo |
|---|---|---|---|
| 2.1 | Sơ đồ luồng dữ liệu 4 tầng, 3 nơi lưu | 20 câu hỏi ra cùng đáp án trên 3 engine | Tổng quan (đổi `DATA_BACKEND`) |
| 2.2 | Sơ đồ constellation, grain 4 fact, bảng ảnh chụp SV-tuần | Ở 5× trên PostgreSQL, bảng rộng gấp đôi dung lượng và chậm gấp 1,56 lần star ở BR2 | Chất lượng & benchmark |
| 3.1 | Bảng vấn đề dữ liệu → cách xử lý; test chống rò rỉ nhãn | Đảo nhãn, danh sách cảnh báo vẫn 3.958 SV | Cảnh báo sớm & rút lui |
| 3.2 | Batch và stream (thư mục, Kafka có watermark); 4 ví dụ tối ưu | Stream lệch 0 dòng so với batch; watermark giữ trạng thái nhỏ hơn ~10×; mart giảm 330× | Click thời gian thực (mở trước, rồi chạy `make stream-kafka STREAM_ARGS="--produce --to-bq --delay 1"`: đường stream dâng lên khớp batch); Spark UI tab Structured Streaming; Hoạt động học tập (đọc mart BR2) |

Dashboard không phải chuẩn đầu ra riêng, nhưng **phần Project chấm nó nặng**: theo file yêu cầu môn, slide và video
Project có tiêu chí Hiện thực ứng dụng 8/10 (mỗi BR demo thành công được 4/n/10, n = 3) và Thiết kế giao diện 2/10. Vì
vậy video phải demo đủ 8 BR trên dashboard. Slide và kịch bản theo các tiêu chí này nằm ở
[slides_outline.md](slides_outline.md) và [presentation_script.md](presentation_script.md).

### Chuẩn bị trước buổi demo

- Bật app xong phải khởi động Streamlit riêng, vì container `app` chỉ chạy `sleep infinity`. Lần nào khởi động lại
  container cũng phải chạy lại lệnh này:
  `docker compose up -d app` rồi `docker compose exec -d app bash -c "cd /work && make app"`, mở http://localhost:8501.
- Mở thử các trang demo trong bảng trên trước giờ thuyết trình. BigQuery Sandbox tự xóa bảng sau 60 ngày; nếu trang
  báo lỗi không tìm thấy bảng thì nạp lại kho và dựng lại mart (`make marts`).
- Lần mở đầu tiên của mỗi trang chờ BigQuery vài giây, sau đó kết quả được lưu tạm. Nên mở trước một lượt để lúc demo
  trang hiện ngay.
- Các lựa chọn khớp với số trong báo cáo: Hoạt động học tập và Cảnh báo sớm chọn BBB 2014J, tuần 4; Tiến độ so với lớp
  chọn AAA 2014J, tuần 10.

## Câu hỏi thi nên ôn, và chỗ có ví dụ trong project

| Câu hỏi | Ví dụ |
|---|---|
| Khác nhau giữa 3 mức ý niệm, luận lý, vật lý? | [design_levels.md](design_levels.md) mục 4 |
| 1NF, 2NF, 3NF là gì; dữ liệu OULAD vi phạm dạng nào? | [design_levels.md](design_levels.md) mục 2.4 |
| Vì sao kho dữ liệu cố ý phi chuẩn hóa? Cái giá là gì? | [design_levels.md](design_levels.md) mục 2.4, [benchmark.md](benchmark.md) kết luận |
| Khi nào dùng 3NF, star, bảng rộng, dạng lồng, tài liệu, khóa-giá trị? | [data_models.md](data_models.md) mục 4 |
| Grain là gì; bảng ảnh chụp khác bảng giao dịch thế nào? | [design_levels.md](design_levels.md) mục 2, [contract.md](contract.md) |
| Rò rỉ nhãn là gì, kiểm bằng cách nào? | [report_tv1.md](report_tv1.md) mục 3.4 |
| Phân vùng, gom cụm, chỉ mục khác nhau thế nào; hợp với engine nào? | [optimization.md](optimization.md) |
| Batch khác stream thế nào; micro-batch, trạng thái, `outputMode`? | [report_tv1.md](report_tv1.md) mục 4 |
| Thời gian sự kiện khác thời gian xử lý thế nào; watermark là gì, đánh đổi gì? | [report_tv1.md](report_tv1.md) mục 4.2 |
| Vì sao dùng `update` mà không dùng `append` khi có watermark? | [report_tv1.md](report_tv1.md) mục 4.2 |
| Làm sao để stream không trùng, không mất (exactly-once)? | [report_tv1.md](report_tv1.md) mục 4.2 |
| Kafka partition và key dùng để làm gì? | [report_tv1.md](report_tv1.md) mục 4.2 |
| Airflow khác `make all` hay cron thế nào? Vì sao bật retries được? | [report_tv1.md](report_tv1.md) mục 1.4 |
| CDC là gì; nạp tăng dần khi không có `MERGE` thì làm sao? | [report_tv1.md](report_tv1.md) mục 4.3, 8.2 |
| Project còn thiếu gì so với production? | [report_tv1.md](report_tv1.md) mục 8.3 |
