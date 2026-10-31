# OULAD Data Warehouse

Kho dữ liệu cho bộ Open University Learning Analytics Dataset (OULAD): ETL bằng Spark, kho chính trên BigQuery,
kho đối chứng trên PostgreSQL, dashboard Streamlit.

```
7 file CSV ──Spark──> staging (Parquet) ──Spark──> 5 dim + 4 fact (Parquet) ──┬──> BigQuery   (kho chính)
                                                                              └──> PostgreSQL (đối chứng)
studentVle ──chia theo ngày──┬──> phát lại vào thư mục ──Spark Structured Streaming──> click theo tuần
                             └──> producer ──> Kafka ──Spark Structured Streaming + watermark──> click theo tuần
```

Tên bảng, tên cột, định nghĩa từng cờ: **[docs/contract.md](docs/contract.md)**. Đọc file này trước khi viết SQL.

## Cài một lần

1. Cài **Docker Desktop** (Windows: bật WSL2). Vào Settings → Resources, cấp **ít nhất 4 GB RAM** (nên 6 GB).
2. Clone repo:
   ```bash
   git clone https://github.com/AdonisKing2003/data_engineer_project.git oulad && cd oulad
   ```
3. Nhận từ TV1 qua **tin nhắn riêng** (không qua GitHub, không qua nhóm chat chung):
   - file `.env`: đặt ở thư mục gốc repo (cạnh `docker-compose.yml`);
   - file `gcp-key.json`: đặt vào `secrets/`.

   Hoặc tự tạo `.env` từ mẫu: `cp .env.example .env` (Windows PowerShell: `copy .env.example .env`), rồi điền `GCP_PROJECT_ID`.
4. Đặt 7 file CSV của OULAD vào `data/raw/` (xin TV1 file zip, hoặc tải ở trang OULAD của Open University):
   ```
   data/raw/courses.csv  assessments.csv  vle.csv  studentInfo.csv
            studentRegistration.csv  studentAssessment.csv  studentVle.csv
   ```
   Các file phải nằm **ngay trong** `data/raw/`, không nằm trong thư mục con.

## Chạy

```bash
docker compose up -d --build            # lần đầu build mất 5–10 phút
docker compose exec app make check      # 5 dòng [OK ]: Spark, DuckDB, Streamlit, PostgreSQL, BigQuery
docker compose exec app make all        # CSV -> kho -> BigQuery + PostgreSQL -> test, khoảng 5 phút
```

`make all` chạy lần lượt staging, dims, facts, student-week, load-bq, load-pg, test và dừng ở bước đầu tiên bị lỗi.
Chạy xong sẽ in bảng tóm tắt, mọi dòng phải là `OK`, và ghi thời gian từng bước ra [docs/etl_timing.md](docs/etl_timing.md).
Chạy lại bao nhiêu lần cũng được: mọi bước đều ghi đè, không nhân đôi dữ liệu.

Chưa có khóa Google Cloud thì dùng `make all-local` (bỏ bước BigQuery).

Mở app:
```bash
docker compose exec app make app        # rồi mở http://localhost:8501
```
App mặc định đọc BigQuery; đặt `DATA_BACKEND=duckdb` trong `.env` để đọc kho Parquet cục bộ. Thanh bên trái chia trang
theo vai trò: Tổng quan, Giảng viên, Cố vấn học tập, Lãnh đạo khoa, Sinh viên, Hệ thống (benchmark, click thời gian thực). Trang Hoạt động học tập
có thêm lựa chọn Toàn trường: tổng click của mọi lượt đăng ký theo loại học liệu và theo tuần. Ba trang của TV2
(`app/pages/`: Nộp bài & điểm, Cảnh báo sớm & rút lui, Tiến độ so với lớp) giữ nguyên bản của TV2: chọn đợt ở thanh bên,
đọc DuckDB qua `app/db.py`. Muốn dùng chung đợt với các trang khác thì gọi `select_offering` trong `app/state.py`.

Lệnh `make` chạy **bên trong container**, nên dùng được trên mọi máy, kể cả Windows.
Mở shell trong container: `docker compose exec app bash`. Tắt: `docker compose down` (dữ liệu PostgreSQL vẫn giữ).

## Từng bước

Chạy riêng từng bước bằng `docker compose exec app make <lệnh>`. Thời gian đo trên máy 16 CPU, 15 GB RAM.

| Lệnh | Việc | Làm gì | Thời gian |
|---|---|---|---|
| `make check` | 1.1b | Kiểm tra đồ nghề trong container | vài giây |
| `make bq-test` | 1.2 | Nạp thử bảng courses lên BigQuery | vài giây |
| `make staging` | 1.3 | 7 CSV → `data/staging/`, đặt kiểu, "?" và ô trống thành NULL, so số dòng | ~45 s |
| `make dims` | 1.4 | Làm sạch, 5 dimension + `fact_enrollment` → `data/warehouse/` | ~30 s |
| `make facts` | 1.5 | `fact_vle_daily` (gộp click trùng) + `fact_submission` | ~40 s |
| `make student-week` | 1.8 | `fact_student_week` (SV × đợt × tuần, as-of) | ~65 s |
| `make load-bq` | 1.6 | Nạp mọi bảng lên BigQuery, so số dòng | ~80 s |
| `make load-pg` | 1.7 | Nạp mọi bảng vào PostgreSQL, so số dòng | ~35 s |
| `make test` | 1.10 | Toàn bộ pytest | ~20 s |
| `make stream` | 1.9 | Phát lại click theo ngày qua Spark Streaming, so với batch | ~2 phút |
| `make stream-kafka` | | Như trên nhưng nguồn là Kafka, gom theo cửa sổ tuần có watermark; cần bật Kafka trước (xem [Demo phần stream](#demo-phần-stream)). Thêm `STREAM_ARGS="--produce --to-bq"` để ghi kết quả lên BigQuery cho dashboard | ~2,5 phút, ~4,5 phút nếu có BigQuery |
| `make all` | 1.13 | Tất cả các bước trên trừ stream | ~5 phút |
| `make scale` | 1.12 | Sinh kho 5× cho benchmark, nạp vào BigQuery `oulad_5x` và PostgreSQL schema `x5` (chạy sau `make all`) | xem dưới |
| `make optimize` | 1.11 | 4 ví dụ tối ưu có số đo, ghi [docs/optimization.md](docs/optimization.md) (chạy sau `make all` và `python scripts/build_tv3_marts.py --apply`) | ~1 phút |
| `make bench` | 3.9 | Benchmark star / 3NF / bảng rộng trên PostgreSQL và BigQuery, 1× và 5×, có kiểm đáp án từng lượt; ghi `bench/results/<run_id>/`. Phải đặt `CONFIRM_M3=1` (sau mốc kiểm tra cuối tuần 2): `docker compose exec -e CONFIRM_M3=1 app make bench`. Quy trình ở [docs/benchmark.md](docs/benchmark.md), cần `make scale` và dựng bố trí theo [docs/layouts.md](docs/layouts.md) | ~10 phút |
| `make models` | | Dựng 2 mô hình phi quan hệ (BigQuery dạng lồng, PostgreSQL JSONB) và đo so với bảng phẳng, ghi [docs/data_models.md](docs/data_models.md) | ~1 phút |

## Kiểm thử

`make test` chạy toàn bộ bộ kiểm thử (283 test, gồm đáp án 20 câu hỏi mẫu trên SQL và trên dashboard, test app và test benchmark). Bảng nào chưa dựng thì test của bảng đó tự bỏ qua.

| File | Kiểm gì |
|---|---|
| `tests/test_staging.py` | Số dòng 7 bảng staging, cột ngày là số nguyên; các phụ thuộc hàm làm căn cứ chuẩn hóa ([docs/design_levels.md](docs/design_levels.md) mục 2.4) |
| `tests/test_warehouse.py` | Mọi con số ở cột **Kiểm** của `docs/contract.md`, số NULL từng cột, khóa chính không trùng, khóa ngoại không mồ côi, tổng click và tổng điểm khớp nguồn |
| `tests/test_student_week.py` | `fact_student_week` ra đúng đáp án BR4, BR7 trong tài liệu đặc tả; chống rò rỉ nhãn `final_result` |
| `tests/test_postgres.py` | Cùng bộ số đó, chạy trên PostgreSQL |
| `tests/test_pipeline.py` | Chạy lại không nhân đôi; bản stream (đọc thư mục và đọc Kafka) khớp bản batch; bản Kafka không bỏ dòng nào vì watermark; bản trên BigQuery khớp bản Parquet |
| `tests/test_tv2_sql.py` | BR1, BR4, BR5, BR7 ra đúng đáp án (TV2) |
| `tests/test_questions.py` | 20 file `sql/questions/qNN.sql` ra đúng đáp án câu hỏi mẫu; đảo nhãn `final_result` rồi chạy lại câu 14 thì danh sách cảnh báo không đổi |
| `tests/test_tv3_*.py` | Mart BR2, BR3; các trang Học phần, Khoa, Sinh viên ra đúng đáp án BR2, BR3, BR6, BR8 (TV3). `RUN_TV3_BIGQUERY_DEMO=1` để chạy trên BigQuery |
| `tests/test_benchmark_*.py` | Runner benchmark mới: ma trận 44/48 ô, cổng câu hỏi, kiểm đáp án từng lượt; trang Chất lượng chỉ hiện lượt chạy thành công (TV3) |
| `tests/test_dashboard_questions.py` | Chấm 20 câu hỏi mẫu qua dashboard: mở đúng trang, chọn đợt/tuần như đề hỏi, tìm đáp án trong nội dung trang. Câu dashboard chưa trả lời được đánh dấu xfail; xem bằng `pytest -rx` |
| `tests/test_app.py` | Mọi trang dashboard mở được không lỗi; số ở trang Tổng quan khớp contract; đợt học được giữ khi đổi trang |

## Demo phần stream

Click của `studentVle` được phát lại theo từng ngày, Spark Structured Streaming cộng dồn click theo SV × đợt × tuần,
rồi so với bảng `fact_student_week` của bản batch. Đây là **phát lại có kiểm soát** dữ liệu lịch sử, không phải luồng
thời gian thực. Có hai nguồn, cùng ra một kết quả; chi tiết và số đo ở [docs/report_tv1.md](docs/report_tv1.md) mục 4.

### Nguồn là thư mục

Một script thả lần lượt file click của từng ngày vào thư mục `data/stream/input/`; Spark đọc thư mục đó.

Chạy một lệnh: `docker compose exec app make stream`. Muốn xem từng micro-batch khi demo, mở hai terminal:
```bash
docker compose exec app python stream/split_days.py                      # một lần, chia file theo ngày
docker compose exec app spark-submit stream/stream_weekly.py             # terminal 1: chạy trước
docker compose exec app python stream/replay.py --delay 1                # terminal 2: phát lại
docker compose exec app python stream/compare.py                         # so với batch
```

### Nguồn là Kafka, có watermark

Producer gửi từng dòng click thành một message JSON lên topic `oulad.clicks` (4 partition, key là `id_student`).
Spark đọc topic, gom click theo cửa sổ 7 ngày theo thời gian sự kiện, có watermark 7 ngày.

Kafka nằm trong profile `stream` nên không tự chạy với `docker compose up -d`. Bật rồi chạy:
```bash
docker compose --profile stream up -d                   # app, postgres và kafka
docker compose exec app make stream-kafka               # tạo lại topic, gửi click, xử lý, so với batch
```
Lần đầu Spark tải gói Kafka connector về `.ivy2/` (cần mạng), các lần sau dùng lại.

Muốn xem từng micro-batch khi demo, mở hai terminal:
```bash
docker compose exec app python stream/split_days.py                                     # một lần
docker compose exec app spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
    --conf spark.jars.ivy=/work/.ivy2 stream/stream_kafka.py                            # terminal 1: chạy trước
docker compose exec app python stream/produce_kafka.py --delay 1                        # terminal 2: gửi click
docker compose exec app python stream/compare.py --source kafka                         # so với batch
```

Ghi kết quả lên BigQuery và xem trên dashboard: thêm `--to-bq`. Mỗi micro-batch được nạp vào bảng
`stream_student_week_updates`, view `stream_student_week_latest` lấy bản mới nhất. Trang **Hệ thống → Click thời gian thực**
đọc view đó và tự tải lại mỗi 10 giây, nên mở trang trước rồi chạy stream sẽ thấy đường stream dâng dần lên khớp batch:
```bash
docker compose exec app make app                                                    # terminal 1, mở http://localhost:8501
docker compose exec app make stream-kafka STREAM_ARGS="--produce --to-bq --delay 1" # terminal 2, khoảng 6 phút
```
Mỗi lần trang tự tải lại quét khoảng 48 MB trên BigQuery. Xem xong thì tắt nút "Tự tải lại" hoặc đóng trang.

Thử dữ liệu đến trễ: `make stream-kafka STREAM_ARGS="--produce --late 0.001"` giữ lại 0,1% số click và gửi sau cùng.
Spark bỏ các click đã quá watermark và đếm ở `rows_dropped_by_watermark` trong `data/stream/_run_kafka.json`, nên
lần chạy này **cố ý** lệch so với batch. Chạy lại `make stream-kafka` không kèm `--late` để test xanh trở lại.

Trong lúc chạy, http://localhost:4040 (tab Structured Streaming) hiện số dòng vào/ra của từng micro-batch.

## Truy cập kho

| Kho | Cách vào |
|---|---|
| BigQuery | Dataset `oulad` trong project ở `GCP_PROJECT_ID`. Trong SQL: `` `oulad.fact_enrollment` `` |
| PostgreSQL | Từ máy thật: `localhost:5432`, user / mật khẩu / database đều là `oulad` (DBeaver, pgAdmin...). Từ container: host `postgres` |
| Parquet | `data/warehouse/<bảng>/`. Đọc nhanh bằng DuckDB: `select * from read_parquet('data/warehouse/dim_week/*.parquet')` |

### Kho 1× và 5× cho benchmark (việc 1.12)

`make scale` chép mỗi SV thành 5 bản (`id_student` của bản i = mã gốc + i × 10.000.000), kéo theo toàn bộ
lượt đăng ký, click, bài nộp và các tuần. Bảng môn, bài, học liệu, tuần giữ nguyên. Vì chép nguyên vẹn nên mọi
tỷ lệ trên kho 5× bằng kho 1×; dùng điều này để kiểm SQL benchmark ra đúng.

| | Kho 1× | Kho 5× |
|---|---|---|
| BigQuery | dataset `oulad` | dataset `oulad_5x` |
| PostgreSQL | schema `public` | schema `x5` |
| Parquet | `data/warehouse/` | `data/warehouse_5x/` |

Viết SQL benchmark **không ghi tên dataset/schema trước tên bảng**, rồi chọn kho lúc chạy, để một câu SQL chạy được trên cả hai kho:
- PostgreSQL: `SET search_path TO x5;` (hoặc `public` cho 1×).
- BigQuery (Python): `bigquery.QueryJobConfig(default_dataset=f"{project}.oulad_5x")`.

## Thư mục

| Thư mục | Nội dung |
|---|---|
| `etl/` | Spark batch: `01_staging` → `02_clean_dims` → `03_facts` → `06_student_week`; `04_load_bq`, `05_load_pg` nạp kho |
| `stream/` | Chia click theo ngày; phát lại vào thư mục hoặc gửi lên Kafka; Spark Structured Streaming; so với batch |
| `scripts/` | `check_env.py`, `bq_smoke_test.py`, `run_all.py` (`make all`) |
| `sql/` | Truy vấn các BR |
| `app/` | Streamlit |
| `tests/` | pytest |
| `bench/` | Benchmark |
| `docs/` | `contract.md` (hợp đồng tên bảng), `etl_timing.md` (thời gian ETL), ghi chú tối ưu; `lo_traceability.md` (chuẩn đầu ra → bằng chứng) |
| `data/` | CSV gốc, Parquet, dữ liệu stream: **không commit** |
| `secrets/` | Khóa Google Cloud: **không commit** |

## Lỗi hay gặp

- **`FileNotFoundError: ... data/raw/courses.csv`**: chưa đặt CSV vào `data/raw/`, hoặc CSV đang nằm trong thư mục con. Xem bước 4 phần Cài một lần.
- **`make check` báo `[SAI] BigQuery`**: thiếu `secrets/gcp-key.json`, hoặc `.env` chưa có `GCP_PROJECT_ID`. Chưa có khóa thì vẫn chạy được `make all-local`.
- **Spark báo `OutOfMemoryError`**: tăng RAM cho Docker Desktop lên 6 GB, hoặc đặt `SPARK_DRIVER_MEMORY=4g` trong `.env`.
- **Cổng 5432 đã bị dùng** (máy đã cài sẵn PostgreSQL): đổi dòng `"5432:5432"` thành `"5433:5432"` trong `docker-compose.yml`.
- **Windows báo lỗi xuống dòng trong script** (`\r`): `git config --global core.autocrlf input` rồi clone lại.
- **Máy Linux không xóa được file trong `data/`** (file do container tạo thuộc root): chạy `make all` một lần, cuối lệnh này trả quyền file về cho bạn. Hoặc `sudo rm -rf data/staging data/warehouse data/stream`.
- **`make stream-kafka` báo không kết nối được `kafka:9092`**: chưa bật Kafka. Chạy `docker compose --profile stream up -d`.
  Dòng `Coordinator load in progress: retrying` lúc mới chạy chỉ là Kafka chưa khởi động xong, producer tự thử lại.
- **Build treo lâu ở `apt-get update` rồi báo `Temporary failure resolving 'deb.debian.org'`**: container không phân giải
  được tên miền, hay gặp khi máy bật VPN (Cloudflare WARP...). Đặt DNS cho Docker trong `/etc/docker/daemon.json`:
  `{"dns": ["1.1.1.1", "8.8.8.8"]}`, rồi `sudo systemctl restart docker`. Hoặc build bằng mạng của máy:
  `docker build --network host -t oulad-app:latest .`
- **Bảng trên BigQuery tự mất sau 60 ngày**: project đang ở chế độ BigQuery Sandbox (miễn phí, bảng hết hạn sau 60 ngày). Chạy lại `make load-bq` là có lại.

Dữ liệu: Kuzilek, J., Hlosta, M., Zdrahal, Z. (2017). *Open University Learning Analytics dataset*. Scientific Data 4, 170171. Giấy phép CC BY 4.0.
