# Chạy TRONG container:  docker compose exec app make <lệnh>
# (Máy Windows không có make thì gõ thẳng lệnh ở dòng bên dưới mỗi mục)

.PHONY: all all-local check bq-test staging dims facts student-week load-bq load-pg stream scale test app

all:          ## 1.13 chạy hết: staging -> dims -> facts -> student-week -> BigQuery -> PostgreSQL -> test
	python scripts/run_all.py

all-local:    ## như all nhưng bỏ BigQuery (máy chưa có khóa Google Cloud)
	python scripts/run_all.py --skip-bq

check:        ## 1.1b kiểm tra Spark, DuckDB, Streamlit, PostgreSQL, BigQuery
	python scripts/check_env.py

bq-test:      ## 1.2 nạp thử courses lên BigQuery
	python scripts/bq_smoke_test.py

staging:      ## 1.3 đọc 7 CSV vào data/staging
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 01_staging.py

dims:         ## 1.4 làm sạch, 5 dimension + fact_enrollment vào data/warehouse
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 02_clean_dims.py

facts:        ## 1.5 fact_vle_daily + fact_submission (chạy sau dims)
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 03_facts.py

student-week: ## 1.8 fact_student_week (chạy sau facts)
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 06_student_week.py

load-bq:      ## 1.6 nạp mọi bảng trong data/warehouse lên BigQuery, so số dòng
	cd etl && python 04_load_bq.py

load-pg:      ## 1.7 nạp mọi bảng trong data/warehouse vào PostgreSQL, so số dòng
	cd etl && python 05_load_pg.py

stream:       ## 1.9 chia click theo ngày, phát lại qua Spark Streaming, so với batch (chạy sau student-week)
	python stream/split_days.py
	spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} stream/stream_weekly.py --replay
	python stream/compare.py

scale:        ## 1.12 sinh kho 5× rồi nạp vào BigQuery (dataset oulad_5x) và PostgreSQL (schema x5); chạy sau all
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 07_scale.py --factor 5
	cd etl && python 04_load_bq.py --scale 5
	cd etl && python 05_load_pg.py --scale 5

test:
	pytest -q

app:
	streamlit run app/Home.py --server.address 0.0.0.0 --server.port 8501
