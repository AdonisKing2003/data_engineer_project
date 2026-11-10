# Thời gian ETL (việc 1.13)

Đo lúc 10/11/2026 16:24 bằng `make all`. Máy: 16 CPU, 15 GB RAM (nhìn từ container), Spark 3.5.3, driver memory 3g.
File này do `scripts/run_all.py` tự sinh; chạy lại `make all` để cập nhật.

## Từng bước

Thời gian thực của cả bước, gồm cả khởi động Spark.

| Việc | Lệnh | Nội dung | Thời gian (s) | Kết quả |
|---|---|---|---:|---|
| 1.3 | `make staging` | 7 CSV -> staging Parquet | 30.8 | OK |
| 1.4 | `make dims` | làm sạch, 5 dimension + fact_enrollment | 22.4 | OK |
| 1.5 | `make facts` | fact_vle_daily + fact_submission | 22.4 | OK |
| 1.8 | `make student-week` | fact_student_week | 38.6 | OK |
| 1.6 | `make load-bq` | nạp kho lên BigQuery | 92.5 | OK |
| 1.11 | `make marts` | dựng lại 2 data mart của app trên BigQuery | 21.6 | OK |
| 1.7 | `make load-pg` | nạp kho vào PostgreSQL | 55.1 | OK |
| 1.10 | `make test` | pytest | 45.9 | OK |
| | | **Tổng** | **329.3** | |

## Staging (1.3)

| Bảng | File nguồn | Số dòng | Ghi Parquet (s) |
|---|---|---:|---:|
| `stg_courses` | courses.csv | 22 | 5.9 |
| `stg_assessments` | assessments.csv | 206 | 1.2 |
| `stg_vle` | vle.csv | 6,364 | 1.0 |
| `stg_student_info` | studentInfo.csv | 32,593 | 1.8 |
| `stg_student_registration` | studentRegistration.csv | 32,593 | 1.2 |
| `stg_student_assessment` | studentAssessment.csv | 173,912 | 1.9 |
| `stg_student_vle` | studentVle.csv | 10,655,280 | 12.2 |

## Kho (1.4, 1.5, 1.8) và nạp kho (1.6, 1.7)

Thời gian ghi Parquet tính từ lúc bắt đầu ghi đến lúc đếm lại xong, không gồm khởi động Spark.

| Bảng | Đầu vào | Số dòng vào | Số dòng ra | Ghi Parquet (s) | Lên BigQuery (s) | Vào PostgreSQL (s) |
|---|---|---:|---:|---:|---:|---:|
| `dim_presentation` | courses | 22 | 22 | 3.0 | 7.5 | 0.0 |
| `dim_student` | studentInfo (distinct SV) | 32,593 | 28,785 | 1.0 | 7.0 | 0.3 |
| `dim_assessment` | assessments | 206 | 206 | 1.4 | 7.1 | 0.1 |
| `dim_vle_site` | vle | 6,364 | 6,364 | 0.9 | 6.5 | 0.1 |
| `dim_week` | sinh từ tuần −4..38 | – | 43 | 0.5 | 6.3 | 0.0 |
| `fact_enrollment` | studentInfo ⨝ studentRegistration | 32,593 | 32,593 | 3.7 | 7.5 | 0.3 |
| `fact_vle_daily` | studentVle (gộp click trùng) | 10,655,280 | 8,459,320 | 11.5 | 26.2 | 36.9 |
| `fact_submission` | studentAssessment | 173,912 | 173,912 | 1.5 | 8.1 | 0.6 |
| `fact_student_week` | fact_enrollment × tuần | 32,593 | 1,342,949 | 28.6 | 12.0 | 14.7 |
