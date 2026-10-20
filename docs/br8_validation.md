# BR8 — Forumng tuần 5 của nhóm đạt

## Câu hỏi và quy tắc

Q20 chỉ kiểm tra BBB 2013J, tuần 5, hoạt động `forumng`. Cohort được lấy từ enrollment có `final_result` là `Pass` hoặc `Distinction`. Click được tổng hợp theo sinh viên; sinh viên không có click forumng vẫn nằm trong mẫu với giá trị 0. Kết quả mô tả phân bố click, không diễn giải hoạt động là nguyên nhân của kết quả học tập.

Truy vấn DuckDB và BigQuery nằm ở `sql/br8_forum_week5.sql` và `sql/bigquery/br8_forum_week5.sql`. Câu hỏi mẫu để chạy trên BigQuery là `sql/questions/q20.sql`.

## Kết quả chuẩn

| Cohort | n | Q1 | Trung vị | Q3 |
|---|---:|---:|---:|---:|
| Pass/Distinction, BBB 2013J, tuần 5 | 1.072 | 0 | 5 | 22 |

## Chạy và xác minh

Chạy trên Parquet/DuckDB:

```powershell
docker compose run --rm --no-deps app python scripts/run_sql.py sql/br8_forum_week5.sql --engine duckdb
```

Chạy Q20 trên BigQuery (cần `GCP_PROJECT_ID`, `BQ_DATASET` và Google credentials):

```powershell
docker compose run --rm --no-deps app python scripts/run_sql.py sql/questions/q20.sql --engine bq
```

Dashboard dùng `DATA_BACKEND=bigquery` mặc định. Để kiểm tra giao diện cục bộ với Parquet, đặt rõ `DATA_BACKEND=duckdb`:

```powershell
docker compose run --rm --no-deps -e DATA_BACKEND=duckdb app python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('app/Home.py').run(); assert not at.exception; print('Dashboard page:', len(at.get('plotly_chart')), 'charts')"
```

Xác minh DuckDB và BigQuery ngày 19/10/2026 đều trả một dòng: `n_students=1072`, `q25_forum_clicks=0`, `median_forum_clicks=5`, `q75_forum_clicks=22`. Truy vấn BigQuery quét 381,8 MB.
