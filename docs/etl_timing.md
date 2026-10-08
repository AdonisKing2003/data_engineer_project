# Thời gian ETL (việc 1.13)

Đo lúc 08/10/2026 16:55 bằng `make all`. Máy: 16 CPU, 15 GB RAM (nhìn từ container), Spark 3.5.3, driver memory 3g.
File này do `scripts/run_all.py` tự sinh; chạy lại `make all` để cập nhật.

## Từng bước

Thời gian thực của cả bước, gồm cả khởi động Spark.

| Việc | Lệnh | Nội dung | Thời gian (s) | Kết quả |
|---|---|---|---:|---|
| 1.3 | `make staging` | 7 CSV -> staging Parquet | 43.2 | OK |
| 1.4 | `make dims` | làm sạch, 5 dimension + fact_enrollment | 31.5 | OK |
| 1.5 | `make facts` | fact_vle_daily + fact_submission | 41.5 | OK |
| 1.8 | `make student-week` | fact_student_week | 65.1 | OK |
| 1.6 | `make load-bq` | nạp kho lên BigQuery | 81.1 | OK |
| 1.7 | `make load-pg` | nạp kho vào PostgreSQL | 33.3 | OK |
| 1.10 | `make test` | pytest | 17.7 | OK |
| | | **Tổng** | **313.5** | |

## Staging (1.3)

| Bảng | File nguồn | Số dòng | Ghi Parquet (s) |
|---|---|---:|---:|
| `stg_courses` | courses.csv | 22 | 8.7 |
| `stg_assessments` | assessments.csv | 206 | 2.2 |
| `stg_vle` | vle.csv | 6,364 | 2.0 |
| `stg_student_info` | studentInfo.csv | 32,593 | 2.8 |
| `stg_student_registration` | studentRegistration.csv | 32,593 | 1.6 |
| `stg_student_assessment` | studentAssessment.csv | 173,912 | 2.4 |
| `stg_student_vle` | studentVle.csv | 10,655,280 | 16.9 |

## Kho (1.4, 1.5, 1.8) và nạp kho (1.6, 1.7)

Thời gian ghi Parquet tính từ lúc bắt đầu ghi đến lúc đếm lại xong, không gồm khởi động Spark.

| Bảng | Đầu vào | Số dòng vào | Số dòng ra | Ghi Parquet (s) | Lên BigQuery (s) | Vào PostgreSQL (s) |
|---|---|---:|---:|---:|---:|---:|
| `dim_presentation` | courses | 22 | 22 | 3.6 | 7.1 | 0.0 |
| `dim_student` | studentInfo (distinct SV) | 32,593 | 28,785 | 1.3 | 5.8 | 0.2 |
| `dim_assessment` | assessments | 206 | 206 | 1.9 | 6.8 | 0.4 |
| `dim_vle_site` | vle | 6,364 | 6,364 | 2.1 | 8.0 | 0.0 |
| `dim_week` | sinh từ tuần −4..38 | – | 43 | 0.7 | 5.7 | 0.0 |
| `fact_enrollment` | studentInfo ⨝ studentRegistration | 32,593 | 32,593 | 7.9 | 6.3 | 0.3 |
| `fact_vle_daily` | studentVle (gộp click trùng) | 10,655,280 | 8,459,320 | 27.3 | 23.7 | 26.2 |
| `fact_submission` | studentAssessment | 173,912 | 173,912 | 2.6 | 6.0 | 0.6 |
| `fact_student_week` | fact_enrollment × tuần | 32,593 | 1,342,949 | 51.4 | 8.4 | 4.4 |
