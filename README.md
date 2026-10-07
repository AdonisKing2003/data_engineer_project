# OULAD Data Warehouse

Kho dữ liệu cho bộ Open University Learning Analytics Dataset (OULAD): ETL bằng Spark, kho trên BigQuery (đối chứng PostgreSQL), dashboard Streamlit.

## Cài một lần

1. Cài **Docker Desktop** (Windows: bật WSL2). Vào Settings → Resources, cấp **ít nhất 4 GB RAM**.
2. Clone repo:
   ```bash
   git clone <url-repo> oulad && cd oulad
   ```
3. Tạo file `.env` từ mẫu:
   ```bash
   cp .env.example .env        # Windows PowerShell: copy .env.example .env
   ```
   Điền `GCP_PROJECT_ID`. Nhận file khóa `gcp-key.json` từ TV1 (gửi riêng, **không** qua GitHub) và đặt vào `secrets/`.
4. Tải 7 file CSV của OULAD, giải nén vào `data/raw/`:
   ```
   data/raw/courses.csv  assessments.csv  vle.csv  studentInfo.csv
            studentRegistration.csv  studentAssessment.csv  studentVle.csv
   ```

## Chạy

```bash
docker compose up -d --build          # lần đầu build mất 5–10 phút
docker compose exec app make check    # Spark, DuckDB, Streamlit, PostgreSQL, BigQuery đều OK
docker compose exec app make staging  # đọc 7 CSV vào data/staging (Parquet)
docker compose exec app make test
```

Không có `make` (Windows): mở `Makefile` và gõ lệnh tương ứng sau `docker compose exec app`, ví dụ
`docker compose exec app python scripts/check_env.py`.

Mở shell trong container: `docker compose exec app bash`. Tắt: `docker compose down` (dữ liệu PostgreSQL vẫn giữ).

## Thư mục

| Thư mục | Nội dung |
|---|---|
| `etl/` | Spark batch: staging → làm sạch → dim/fact |
| `stream/` | Spark Structured Streaming (phát lại click theo ngày) |
| `sql/` | Truy vấn các BR |
| `app/` | Streamlit |
| `tests/` | pytest |
| `bench/` | Benchmark |
| `docs/` | Ghi chú thiết kế, tối ưu |
| `data/` | CSV gốc và Parquet, **không commit** |
| `secrets/` | Khóa Google Cloud, **không commit** |

## Lỗi hay gặp

- **Spark báo `OutOfMemoryError`**: tăng RAM cho Docker Desktop lên 6 GB, hoặc đặt `SPARK_DRIVER_MEMORY=4g` trong `.env`.
- **Cổng 5432 đã bị dùng** (máy đã cài sẵn PostgreSQL): đổi dòng `"5432:5432"` thành `"5433:5432"` trong `docker-compose.yml`.
- **Windows báo lỗi xuống dòng trong script** (`\r`): `git config --global core.autocrlf input` rồi clone lại.

Dữ liệu: Kuzilek, J., Hlosta, M., Zdrahal, Z. (2017). *Open University Learning Analytics dataset*. Scientific Data 4, 170171. Giấy phép CC BY 4.0.
