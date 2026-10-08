# OULAD Data Warehouse

Kho dữ liệu cho bộ Open University Learning Analytics Dataset (OULAD): ETL bằng Spark, kho chính trên BigQuery,
kho đối chứng trên PostgreSQL, dashboard Streamlit.

```
7 file CSV ──Spark──> staging (Parquet) ──Spark──> 5 dim + 4 fact (Parquet) ──┬──> BigQuery   (kho chính)
                                                                              └──> PostgreSQL (đối chứng)
studentVle ──chia theo ngày──> phát lại vào thư mục ──Spark Structured Streaming──> click theo tuần
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

Mở app (khi đã có `app/Home.py`, việc 3.2):
```bash
docker compose exec app make app        # rồi mở http://localhost:8501
```

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
| `make all` | 1.13 | Tất cả các bước trên trừ stream | ~5 phút |
| `make scale` | 1.12 | Sinh kho 5× cho benchmark, nạp vào BigQuery `oulad_5x` và PostgreSQL schema `x5` (chạy sau `make all`) | xem dưới |

## Kiểm thử

`make test` chạy toàn bộ bộ kiểm thử (150 test). Bảng nào chưa dựng thì test của bảng đó tự bỏ qua.

| File | Kiểm gì |
|---|---|
| `tests/test_staging.py` | Số dòng 7 bảng staging, cột ngày là số nguyên |
| `tests/test_warehouse.py` | Mọi con số ở cột **Kiểm** của `docs/contract.md`, số NULL từng cột, khóa chính không trùng, khóa ngoại không mồ côi, tổng click và tổng điểm khớp nguồn |
| `tests/test_student_week.py` | `fact_student_week` ra đúng đáp án BR4, BR7 trong tài liệu đặc tả; chống rò rỉ nhãn `final_result` |
| `tests/test_postgres.py` | Cùng bộ số đó, chạy trên PostgreSQL |
| `tests/test_pipeline.py` | Chạy lại không nhân đôi; bản stream khớp bản batch |

## Demo phần stream (không dùng Kafka)

Một script thả lần lượt file click của từng ngày vào thư mục `data/stream/input/`; Spark Structured Streaming đọc
thư mục đó và cộng dồn click theo tuần. Đây là **phát lại có kiểm soát** dữ liệu lịch sử, không phải luồng thời gian thực.

Chạy một lệnh: `docker compose exec app make stream`. Muốn xem từng micro-batch khi demo, mở hai terminal:
```bash
docker compose exec app python stream/split_days.py                      # một lần, chia file theo ngày
docker compose exec app spark-submit stream/stream_weekly.py             # terminal 1: chạy trước
docker compose exec app python stream/replay.py --delay 1                # terminal 2: phát lại
docker compose exec app python stream/compare.py                         # so với batch
```

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
| `stream/` | Chia click theo ngày, phát lại, Spark Structured Streaming, so với batch |
| `scripts/` | `check_env.py`, `bq_smoke_test.py`, `run_all.py` (`make all`) |
| `sql/` | Truy vấn các BR |
| `app/` | Streamlit |
| `tests/` | pytest |
| `bench/` | Benchmark |
| `docs/` | `contract.md` (hợp đồng tên bảng), `etl_timing.md` (thời gian ETL), ghi chú tối ưu |
| `data/` | CSV gốc, Parquet, dữ liệu stream: **không commit** |
| `secrets/` | Khóa Google Cloud: **không commit** |

## Lỗi hay gặp

- **`FileNotFoundError: ... data/raw/courses.csv`**: chưa đặt CSV vào `data/raw/`, hoặc CSV đang nằm trong thư mục con. Xem bước 4 phần Cài một lần.
- **`make check` báo `[SAI] BigQuery`**: thiếu `secrets/gcp-key.json`, hoặc `.env` chưa có `GCP_PROJECT_ID`. Chưa có khóa thì vẫn chạy được `make all-local`.
- **Spark báo `OutOfMemoryError`**: tăng RAM cho Docker Desktop lên 6 GB, hoặc đặt `SPARK_DRIVER_MEMORY=4g` trong `.env`.
- **Cổng 5432 đã bị dùng** (máy đã cài sẵn PostgreSQL): đổi dòng `"5432:5432"` thành `"5433:5432"` trong `docker-compose.yml`.
- **Windows báo lỗi xuống dòng trong script** (`\r`): `git config --global core.autocrlf input` rồi clone lại.
- **Máy Linux không xóa được file trong `data/`** (file do container tạo thuộc root): chạy `make all` một lần, cuối lệnh này trả quyền file về cho bạn. Hoặc `sudo rm -rf data/staging data/warehouse data/stream`.
- **Bảng trên BigQuery tự mất sau 60 ngày**: project đang ở chế độ BigQuery Sandbox (miễn phí, bảng hết hạn sau 60 ngày). Chạy lại `make load-bq` là có lại.

Dữ liệu: Kuzilek, J., Hlosta, M., Zdrahal, Z. (2017). *Open University Learning Analytics dataset*. Scientific Data 4, 170171. Giấy phép CC BY 4.0.
