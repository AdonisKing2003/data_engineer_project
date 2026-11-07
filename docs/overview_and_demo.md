# Tổng quan project, công nghệ, chuẩn đầu ra và kịch bản báo cáo

Tài liệu tóm tắt để chuẩn bị báo cáo (tiểu luận) và thuyết trình. Số liệu lấy từ các lần chạy thật ngày 26–31/10/2026;
chi tiết và cách đo nằm ở các file docs được dẫn tới.

---

## 1. Tóm tắt project

**Đề tài.** Kho dữ liệu phân tích học tập cho bộ Open University Learning Analytics Dataset (OULAD), phục vụ 8 yêu
cầu nghiệp vụ (BR1–BR8) và 20 câu hỏi mẫu, hiển thị trên dashboard chia theo vai trò người dùng.

**Dữ liệu nguồn.** 7 file CSV của OULAD (giấy phép CC BY 4.0):

| Chỉ số | Giá trị |
|---|---:|
| Đợt học (học phần × kỳ) | 22 |
| Sinh viên | 28.785 |
| Lượt đăng ký | 32.593 |
| Bài kiểm tra / lần nộp | 206 / 173.912 |
| Học liệu trực tuyến (VLE) | 6.364 |
| Dòng click gốc → sau khi gộp dòng trùng | 10.655.280 → 8.459.320 |
| Tổng lượt click | 39.605.099 |

**8 yêu cầu nghiệp vụ.**

| BR | Câu hỏi | Kết quả tiêu biểu |
|---|---|---|
| BR1 | Nộp bài, điểm và trễ hạn theo loại bài | 16,8% bài TMA nộp trễ |
| BR2 | Hoạt động trên VLE theo tuần và loại học liệu | `oucontent` chiếm 28,3% tổng click |
| BR3 | Click trước bài TMA đầu tiên có liên quan tới điểm không (Spearman) | Có khoảng tin cậy 95% theo từng đợt |
| BR4 | Cảnh báo sớm ở tuần 4 | 3.958 SV vào danh sách, độ chính xác 80,6%, độ phủ 26,9% |
| BR5 | Đường cong rút lui theo tuần | So sánh 22 đợt |
| BR6 | Khoảng cách tỷ lệ đạt giữa nhóm IMD thấp và cao | 41,1% so với 63,3%, chênh 22,2 điểm |
| BR7 | Tiến độ cá nhân so với phân vị của lớp | Dải Q25–Q75 theo tuần |
| BR8 | Hoạt động diễn đàn tuần 5 của nhóm đạt | Trung vị và khoảng tứ phân vị |

**Luồng dữ liệu.**

```
7 file CSV ──Spark──> staging (Parquet) ──Spark──> kho star: 5 dimension + 4 fact (Parquet)
                                                     ├──> BigQuery    (kho chính)    ──> dashboard Streamlit
                                                     └──> PostgreSQL  (kho đối chứng, benchmark)
studentVle ──chia theo ngày──> producer ──> Kafka ──Spark Structured Streaming + watermark──> BigQuery ──> trang Click thời gian thực
Airflow: lập lịch và điều phối toàn bộ nhánh batch, có cổng chất lượng trước khi nạp
```

**Kết quả chính.**

| Hạng mục | Kết quả |
|---|---|
| Dựng lại toàn bộ kho | `make all` 303 s; DAG Airflow 223 s (2 bước nạp chạy song song) |
| Đúng trên nhiều nơi lưu | 20 câu hỏi mẫu ra cùng đáp án trên BigQuery, PostgreSQL, DuckDB |
| Stream | Kafka → Spark có watermark, lệch 0 dòng so với batch trên 1.342.949 dòng; trạng thái lớn nhất nhỏ hơn ~10 lần so với không có watermark |
| Tối ưu (đã áp dụng cho kho chính) | Giảm 5,3× (chỉ mục PostgreSQL) tới 330× (bảng tổng hợp sẵn trên BigQuery) |
| Kiểm thử | 289 test: 288 qua, 1 bỏ qua (test DAG, chạy riêng trong container airflow: 11 qua) |
| Dashboard | 9 trang, chia theo 6 nhóm: Chung, Giảng viên, Cố vấn học tập, Lãnh đạo khoa, Sinh viên, Hệ thống |

**Phân công.** TV1: môi trường, ETL, kho, stream, Airflow, kiểm thử, tối ưu. TV2: BR1, BR4, BR5, BR7 và các trang tương
ứng. TV3: BR2, BR3, BR6, BR8, bảng tổng hợp sẵn cho app, benchmark bố trí dữ liệu, ghép báo cáo.

---

## 2. Công nghệ sử dụng

| Công nghệ | Phiên bản | Vai trò trong project |
|---|---|---|
| Docker, Docker Compose | Compose v2 | Môi trường giống nhau trên mọi máy; Kafka và Airflow tách thành profile, chỉ bật khi cần |
| Python | 3.11 | Ngôn ngữ chung; mọi phiên bản thư viện khóa trong `requirements.lock` (70 gói) |
| Apache Spark (PySpark) | 3.5.3 | ETL batch: staging, làm sạch, dựng dimension và fact, bảng SV-tuần, kho 5× |
| Spark Structured Streaming | 3.5.3 | Xử lý stream micro-batch có trạng thái, cửa sổ thời gian sự kiện, watermark |
| Apache Kafka (KRaft) | 3.8.1 | Hàng đợi sự kiện cho nhánh stream; producer bằng `confluent-kafka` |
| Apache Parquet (`pyarrow`) | | Kho trung gian lưu theo cột, nguồn chung cho mọi engine |
| Google BigQuery (Sandbox) | | Kho chính cho dashboard; phân vùng, gom cụm, dạng lồng `ARRAY<STRUCT>` |
| PostgreSQL | 16 | Kho đối chứng, nền benchmark star / 3NF / bảng rộng, dạng tài liệu JSONB, CSDL của Airflow |
| DuckDB | 1.5.6 | Chạy SQL thẳng trên Parquet tại máy, dùng khi phát triển và trong test |
| Streamlit, Plotly | 1.65.0, 6.9 | Dashboard theo vai trò người dùng |
| Apache Airflow | 2.10.5 | Điều phối pipeline batch: lập lịch, sensor, cổng chất lượng, chạy song song, retries, báo lỗi |
| pytest | 9.2 | 289 test: kho, phụ thuộc hàm, đáp án nghiệp vụ, stream, app, benchmark, DAG |
| Make | | Mỗi bước pipeline là một lệnh `make`, dùng chung cho người chạy tay và cho Airflow |

---

## 3. Công nghệ ứng với chuẩn đầu ra

| Chuẩn đầu ra | Công nghệ và kỹ thuật thể hiện chuẩn đó |
|---|---|
| **1.1** Thiết kế CSDL ở mức ý niệm, luận lý, vật lý | Sơ đồ thực thể (Mermaid); star schema dạng constellation; kiểm phụ thuộc hàm bằng DuckDB; mức vật lý trên Parquet, BigQuery (phân vùng, gom cụm), PostgreSQL (khóa chính, chỉ mục) |
| **1.2** Mô hình hóa từ quan hệ đến phi quan hệ | 7 mô hình: 3NF và star (PostgreSQL, BigQuery), bảng rộng, lưu theo cột (Parquet, BigQuery), dạng lồng (BigQuery `ARRAY<STRUCT>`), tài liệu (PostgreSQL JSONB), khóa-giá trị (state store của Spark) |
| **2.1** Kiến trúc quản lý dữ liệu từ nhiều nguồn | Docker Compose; 4 tầng raw → staging → kho → phục vụ; 3 nơi lưu (BigQuery, PostgreSQL, Parquet/DuckDB); 2 đường nạp batch (Spark) và stream (Kafka + Spark); tầng truy vấn `app/data.py` đổi nơi đọc bằng một biến môi trường; Airflow điều phối |
| **2.2** Thiết kế kho dữ liệu | Mô hình chiều Kimball, 4 fact dùng chung 5 dimension; bảng ảnh chụp SV-tuần chống rò rỉ nhãn; cờ chất lượng thay vì xóa dòng; bảng tổng hợp sẵn trên BigQuery; benchmark star / 3NF / bảng rộng ở 1× và 5× |
| **3.1** Quản lý dữ liệu phức tạp | Spark gộp dòng click trùng; xử lý thiếu, sai định dạng, mâu thuẫn bằng cờ; test chống rò rỉ nhãn; chạy lại không nhân đôi; đối soát trên 3 engine; cổng chất lượng trong Airflow; 289 test |
| **3.2** Xử lý dữ liệu theo kiểu mẫu hiện đại | Xem bảng dưới |

**Các kiểu mẫu xử lý hiện đại (chuẩn 3.2):**

| Kiểu mẫu | Công nghệ | Bằng chứng |
|---|---|---|
| Xử lý phân tán | Spark 3.5 | Toàn bộ ETL batch, sinh kho 5× (42,3 triệu dòng click) |
| Stream theo sự kiện | Kafka + Spark Structured Streaming | Cửa sổ tuần theo thời gian sự kiện, watermark 7 ngày, 0 dòng bị bỏ, lệch 0 so với batch |
| Không trùng, không mất (exactly-once) | Producer idempotent, checkpoint của Spark, ghi theo `batch_id` | Chạy lại một micro-batch không sinh dòng trùng, cả trên Parquet lẫn BigQuery |
| Kho dữ liệu đám mây không máy chủ | BigQuery | Tính tiền theo bytes quét; mọi tối ưu đo bằng bytes |
| Lưu trữ theo cột | Parquet, BigQuery, DuckDB | BigQuery chỉ quét cột cần; DuckDB chạy SQL thẳng trên Parquet |
| Tối ưu có số đo | Phân vùng, gom cụm, bảng tổng hợp sẵn, chỉ mục | 16,8×, 15,9×, 330× bytes quét; 5,3× thời gian |
| Điều phối pipeline | Airflow | Lập lịch, sensor, cổng chất lượng, chạy song song, retries, báo lỗi qua log và webhook |
| Hạ tầng như code, tái lập được | Docker Compose, Makefile, `requirements.lock` | Một lệnh dựng lại toàn bộ; build ở đâu cũng ra cùng một bộ thư viện |

---

## 4. Tài liệu ứng với chuẩn đầu ra

Bảng truy vết đầy đủ (mỗi chuẩn có tài liệu, code, con số và test) nằm ở **[lo_traceability.md](lo_traceability.md)**.
Đây là file nên đưa vào phụ lục báo cáo.

| Chuẩn đầu ra | Tài liệu chính | Tài liệu bổ trợ |
|---|---|---|
| 1.1 Thiết kế CSDL 3 mức | [design_levels.md](design_levels.md) | [contract.md](contract.md) (hợp đồng tên bảng, cột, cờ), [optimization.md](optimization.md) (mức vật lý) |
| 1.2 Quan hệ đến phi quan hệ | [data_models.md](data_models.md) | [benchmark.md](benchmark.md), [layouts.md](layouts.md) (3NF, bảng rộng) |
| 2.1 Kiến trúc nhiều nguồn | [report_tv1.md](report_tv1.md) mục 1, 3, 4.3 | [../README.md](../README.md), [etl_timing.md](etl_timing.md) |
| 2.2 Thiết kế kho | [design_levels.md](design_levels.md) mục 2 | [contract.md](contract.md), [tv3_marts.md](tv3_marts.md), [benchmark.md](benchmark.md) |
| 3.1 Dữ liệu phức tạp | [report_tv1.md](report_tv1.md) mục 3, 5 | [br2_validation.md](br2_validation.md), [br3_validation.md](br3_validation.md), [br6_validation.md](br6_validation.md), [br8_validation.md](br8_validation.md), [task_3_8_validation.md](task_3_8_validation.md) |
| 3.2 Kiểu mẫu hiện đại | [report_tv1.md](report_tv1.md) mục 1.4, 4, 6, 8 | [optimization.md](optimization.md) |

Ánh xạ từ mục báo cáo sang file:

| Phần trong báo cáo | Lấy từ |
|---|---|
| Kiến trúc và luồng dữ liệu | [report_tv1.md](report_tv1.md) mục 1 |
| Thiết kế CSDL và kho | [design_levels.md](design_levels.md), [contract.md](contract.md) |
| Mô hình dữ liệu | [data_models.md](data_models.md) |
| ETL và làm sạch | [report_tv1.md](report_tv1.md) mục 3 |
| Stream | [report_tv1.md](report_tv1.md) mục 4 |
| Điều phối | [report_tv1.md](report_tv1.md) mục 1.4 |
| Kết quả 8 yêu cầu nghiệp vụ | Các file `br*_validation.md`, `sql/questions/` |
| Kiểm thử | [report_tv1.md](report_tv1.md) mục 5 |
| Tối ưu và benchmark | [optimization.md](optimization.md), [benchmark.md](benchmark.md) |
| Hạn chế và hướng phát triển | [report_tv1.md](report_tv1.md) mục 7, 8; bảng hạn chế trong [lo_traceability.md](lo_traceability.md) |

---

## 5. Kiểm thử và demo khi báo cáo

Mọi lệnh chạy ở thư mục gốc repo.

### 5.1 Một ngày trước buổi báo cáo

**Bước 1. Bật môi trường và kiểm tra đồ nghề.**

```bash
docker compose --profile stream up -d          # app, postgres, kafka
docker compose exec app make check             # phải ra 5 dòng [OK ]: Spark, DuckDB, Streamlit, PostgreSQL, BigQuery
```

**Bước 2. Dựng lại kho và chạy toàn bộ test.**

```bash
docker compose exec app make all               # khoảng 5 phút, mọi dòng tóm tắt phải là OK
docker compose exec app make test              # mong đợi: 288 passed, 1 skipped
```

Bảng trên BigQuery Sandbox tự xóa sau 60 ngày kể từ lần nạp. `make all` nạp lại nên luôn an toàn.

**Bước 3. Chạy stream một lần.** Bước này kiểm tra Kafka và BigQuery, đồng thời tải sẵn gói Kafka connector cho Spark
để hôm demo không phải tải lại.

```bash
docker compose exec app make stream-kafka STREAM_ARGS="--produce --to-bq"
docker compose exec app pytest -q tests/test_pipeline.py      # mong đợi: 5 passed
```

**Bước 4. Chạy Airflow một lần để có ảnh Graph và Gantt.**

```bash
docker compose --profile airflow up -d
docker compose exec airflow make test-dag                       # mong đợi: 10 passed
docker compose exec airflow airflow dags trigger oulad_batch    # khoảng 4 phút
docker compose exec airflow cat /opt/airflow/standalone_admin_password.txt
```

Mở http://localhost:8080 (user `admin`) → DAG `oulad_batch`. Chụp tab **Graph** (thứ tự, 2 bước nạp song song) và tab
**Gantt** (thời gian từng bước). Xong thì tạm dừng lịch và tắt để trả RAM:

```bash
docker compose exec airflow airflow dags pause oulad_batch
docker compose --profile airflow stop airflow
```

**Bước 5. Quay video dự phòng** cảnh demo stream ở mục 5.3, phòng khi mạng hoặc BigQuery có vấn đề lúc thuyết trình.

### 5.2 Ngay trước giờ thuyết trình

```bash
docker compose --profile stream up -d
docker compose exec app make app               # mở http://localhost:8501
```

Mở sẵn các tab trình duyệt:

- Dashboard: trang **Tổng quan**, **Cảnh báo sớm & rút lui**, **Khoảng cách IMD**, **Chất lượng & benchmark**,
  **Click thời gian thực**.
- Ảnh Graph và Gantt của Airflow (hoặc bật Airflow nếu máy đủ RAM).
- Một terminal ở thư mục repo, chữ cỡ lớn.

### 5.3 Kịch bản demo theo chuẩn đầu ra

Thuyết trình chấm 4 chuẩn 2.1, 2.2, 3.1, 3.2. Tổng thời gian demo khoảng 10–12 phút.

**Demo 1. Chuẩn 2.1: một câu SQL, ba nơi lưu, cùng đáp án** (khoảng 2 phút)

Slide: sơ đồ luồng dữ liệu ở mục 1. Sau đó chạy câu 18 (BR6) trên cả 3 nơi lưu:

```bash
docker compose exec app python scripts/run_sql.py sql/questions/q18.sql --engine bq
docker compose exec app python scripts/run_sql.py sql/questions/q18.sql --engine pg
docker compose exec app python scripts/run_sql.py sql/questions/q18.sql --engine duckdb
```

Cả 3 đều ra `41.1 / 63.3 / 22.2`. Câu để nói: "20 câu hỏi mẫu viết bằng SQL chung, ra cùng đáp án trên BigQuery,
PostgreSQL và DuckDB. Dashboard đổi nơi đọc chỉ bằng biến `DATA_BACKEND`."

Mở trang **Khoảng cách IMD** để thấy đúng con số đó trên dashboard.

**Demo 2. Chuẩn 2.2: thiết kế kho và so sánh bố trí** (khoảng 2 phút)

Slide: sơ đồ constellation (4 fact, 5 dimension), grain của từng fact, bảng ảnh chụp SV-tuần. Mở trang
**Chất lượng & benchmark**: so star / 3NF / bảng rộng trên 2 engine, ở 1× và 5×.

Câu để nói: "Không bố trí nào thắng ở mọi ô. Nhóm giữ star vì dễ viết SQL nhất và trên PostgreSQL nhanh hơn 3NF."

**Demo 3. Chuẩn 3.1: chống rò rỉ nhãn** (khoảng 2 phút)

Mở trang **Cảnh báo sớm & rút lui** ở tuần 4. Sau đó chạy test đảo nhãn:

```bash
docker compose exec app pytest -v tests/test_questions.py -k label_flip
```

Câu để nói: "Đảo toàn bộ kết quả cuối kỳ (Đạt ↔ Rút, Giỏi ↔ Trượt) rồi chạy lại câu 14: danh sách cảnh báo vẫn đúng
3.958 sinh viên, chỉ độ chính xác thay đổi. Vậy danh sách không dùng thông tin tương lai."

Nhắc thêm: 10,6 triệu dòng click gộp còn 8,46 triệu mà tổng click giữ nguyên; 289 test.

**Demo 4. Chuẩn 3.2: stream trực tiếp** (khoảng 4 phút, cảnh mạnh nhất)

1. Mở trang **Click thời gian thực**, bật nút **Tự tải lại mỗi 10 giây**.
2. Chạy ở terminal:
   ```bash
   docker compose exec app make stream-kafka STREAM_ARGS="--produce --to-bq --delay 1"
   ```
3. Trong khi chạy, giải thích theo slide: producer → Kafka → Spark (cửa sổ tuần, watermark 7 ngày) → BigQuery (bảng
   log ghi thêm + view lấy bản mới nhất) → dashboard. Có thể mở http://localhost:4040, tab Structured Streaming.
4. Đường stream dâng dần lên trùng đường batch đứt nét. Khi xong, trang báo "Stream đã xử lý hết click".
5. Tắt lại nút tự tải lại.

Câu để nói: "Stream lệch 0 dòng so với batch. Có watermark, trạng thái lớn nhất 65 nghìn khóa thay vì 627 nghìn."

Lệnh với `--delay 1` mất khoảng 6 phút. Nếu thời gian ngắn, bỏ `--delay 1` (khoảng 4 phút) hoặc chiếu video dự phòng.

**Demo 5. Chuẩn 3.2: điều phối và tối ưu** (khoảng 2 phút)

Chiếu ảnh Airflow Graph và Gantt: chờ dữ liệu → các bước Spark → cổng chất lượng → 2 bước nạp song song → test.
Câu để nói: "Cổng chất lượng chạy trước khi nạp, lỗi thì BigQuery giữ bản cũ. Task lỗi hẳn thì báo qua log và webhook."

Slide tối ưu: phân vùng 16,8×, gom cụm 15,9×, bảng tổng hợp sẵn 330× (bytes quét BigQuery), chỉ mục 5,3× (PostgreSQL); cả bốn đã nằm trong kho chính.

**Nếu bị hỏi chuẩn 1.1, 1.2** (chấm qua tiểu luận và bài thi, không bắt buộc demo): mở
[design_levels.md](design_levels.md) (sơ đồ 3 mức) và [data_models.md](data_models.md) (7 mô hình, số đo dạng lồng và
JSONB).

### 5.4 Khi demo gặp sự cố

| Sự cố | Cách xử lý |
|---|---|
| Mất mạng hoặc BigQuery lỗi | Tắt `make app` (Ctrl+C), chạy lại `docker compose exec -e DATA_BACKEND=duckdb app make app`: dashboard đọc kho Parquet tại máy. Demo 1 bỏ `--engine bq`. Demo 4 chiếu video |
| `make stream-kafka` báo không kết nối được `kafka:9092` | Chưa bật Kafka: `docker compose --profile stream up -d`, đợi khoảng 20 giây |
| Spark báo hết bộ nhớ | Tắt Airflow (`docker compose --profile airflow stop airflow`) rồi chạy lại |
| Trang Click thời gian thực báo chưa có kết quả | Stream chưa chạy xong micro-batch đầu; đợi vài giây hoặc bấm tải lại |
| Cổng 8501 hoặc 8080 bị chiếm | Xem mục Lỗi hay gặp trong [../README.md](../README.md) |

### 5.5 Câu hỏi hay gặp

Danh sách câu hỏi thi và chỗ có ví dụ nằm ở cuối [lo_traceability.md](lo_traceability.md). Các hạn chế nên chủ động nói
trước nằm trong bảng "Hạn chế cần nói trước khi bị hỏi" của file đó. Ba câu dễ bị hỏi nhất:

| Câu hỏi | Trả lời ngắn | Chi tiết |
|---|---|---|
| Stream có phải luồng thật không? | Là phát lại dữ liệu lịch sử, nhưng nguồn là Kafka và xử lý theo thời gian sự kiện có watermark, đúng như với luồng thật | [report_tv1.md](report_tv1.md) mục 4 |
| Sao không nạp tăng dần, không có CDC? | Nguồn là file tĩnh và BigQuery Sandbox cấm `MERGE`. Nhánh stream đã nạp tăng dần bằng bảng log + view; kiến trúc CDC nếu làm có ở mục 8.2 | [report_tv1.md](report_tv1.md) mục 4.3, 8.2 |
| Còn thiếu gì so với production? | Kafka 1 broker, Spark 1 máy, BigQuery Sandbox, chưa có CI và cảnh báo dữ liệu cũ quá hạn; mỗi mục có lý do và hướng làm | [report_tv1.md](report_tv1.md) mục 8.3 |
