# Thời gian ETL (việc 1.13)

Đo lúc 13/10/2026 03:52 bằng `make all`. Máy: 16 CPU, 8 GB RAM (nhìn từ container), Spark 3.5.3, driver memory 3g.
File này do `scripts/run_all.py` tự sinh; chạy lại `make all` để cập nhật.

## Từng bước

Thời gian thực của cả bước, gồm cả khởi động Spark.

| Việc | Lệnh | Nội dung | Thời gian (s) | Kết quả |
|---|---|---|---:|---|
| 1.3 | `make staging` | 7 CSV -> staging Parquet | 46.0 | OK |
| 1.4 | `make dims` | làm sạch, 5 dimension + fact_enrollment | 38.4 | OK |
| 1.5 | `make facts` | fact_vle_daily + fact_submission | 31.6 | OK |
| 1.8 | `make student-week` | fact_student_week | 33.2 | OK |
| 1.6 | `make load-bq` | nạp kho lên BigQuery | 83.5 | OK |
| 1.7 | `make load-pg` | nạp kho vào PostgreSQL | 25.1 | OK |
| 1.10 | `make test` | pytest | 45.1 | OK |
| | | **Tổng** | **303.0** | |

## Staging (1.3)

| Bảng | File nguồn | Số dòng | Ghi Parquet (s) |
|---|---|---:|---:|
| `stg_courses` | courses.csv | 22 | 6.7 |
| `stg_assessments` | assessments.csv | 206 | 3.6 |
| `stg_vle` | vle.csv | 6,364 | 3.5 |
| `stg_student_info` | studentInfo.csv | 32,593 | 3.7 |
| `stg_student_registration` | studentRegistration.csv | 32,593 | 3.5 |
| `stg_student_assessment` | studentAssessment.csv | 173,912 | 6.1 |
| `stg_student_vle` | studentVle.csv | 10,655,280 | 15.2 |

## Kho (1.4, 1.5, 1.8) và nạp kho (1.6, 1.7)

Thời gian ghi Parquet tính từ lúc bắt đầu ghi đến lúc đếm lại xong, không gồm khởi động Spark.

| Bảng | Đầu vào | Số dòng vào | Số dòng ra | Ghi Parquet (s) | Lên BigQuery (s) | Vào PostgreSQL (s) |
|---|---|---:|---:|---:|---:|---:|
| `dim_presentation` | courses | 22 | 22 | 6.2 | 5.4 | 0.1 |
| `dim_student` | studentInfo (distinct SV) | 32,593 | 28,785 | 2.8 | 5.4 | 0.2 |
| `dim_assessment` | assessments | 206 | 206 | 3.0 | 7.6 | 0.1 |
| `dim_vle_site` | vle | 6,364 | 6,364 | 3.1 | 6.4 | 0.2 |
| `dim_week` | sinh từ tuần −4..38 | – | 43 | 7.8 | 5.5 | 0.5 |
| `fact_enrollment` | studentInfo ⨝ studentRegistration | 32,593 | 32,593 | 5.7 | 7.2 | 0.4 |
| `fact_vle_daily` | studentVle (gộp click trùng) | 10,655,280 | 8,459,320 | 17.4 | 30.0 | 18.7 |
| `fact_submission` | studentAssessment | 173,912 | 173,912 | 3.3 | 5.3 | 0.5 |
| `fact_student_week` | fact_enrollment × tuần | 32,593 | 1,342,949 | 22.1 | 8.2 | 3.2 |
