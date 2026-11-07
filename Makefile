# Chạy TRONG container:  docker compose exec app make <lệnh>
# (Máy Windows không có make thì gõ thẳng lệnh ở dòng bên dưới mỗi mục)

.PHONY: all all-local check bq-test staging dims facts student-week load-bq load-pg load-plain tune marts stream scale optimize models test bench app stream-kafka lock test-dag

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

load-pg:      ## 1.7 nạp mọi bảng trong data/warehouse vào PostgreSQL, so số dòng (kèm chỉ mục cho trang Học phần)
	cd etl && python 05_load_pg.py

marts:        ## dựng lại 2 data mart của app (BR2, BR3) trên BigQuery; chạy sau load-bq
	python scripts/build_tv3_marts.py --apply

load-plain:   ## nạp lại 2 bảng fact lớn KHÔNG tối ưu (bỏ phân vùng, gom cụm, chỉ mục phụ); chạy trước make bench
	cd etl && python 04_load_bq.py --no-tuning fact_student_week fact_vle_daily
	cd etl && python 05_load_pg.py --no-tuning fact_vle_daily
	@echo "Kho đang là bảng thường. Đo xong thì chạy: make load-bq load-pg (hoặc make tune) để bật lại tối ưu."

tune:         ## bật lại tối ưu cho 2 bảng fact lớn sau make load-plain
	cd etl && python 04_load_bq.py fact_student_week fact_vle_daily
	cd etl && python 05_load_pg.py fact_vle_daily

stream:       ## 1.9 chia click theo ngày, phát lại qua Spark Streaming, so với batch (chạy sau student-week)
	python stream/split_days.py
	spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} stream/stream_weekly.py --replay
	python stream/compare.py

KAFKA_PKG = org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3
STREAM_ARGS ?= --produce

stream-kafka: ## stream từ Kafka có watermark; cần: docker compose --profile stream up -d
	python stream/split_days.py
	spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} --packages $(KAFKA_PKG) --conf spark.jars.ivy=/work/.ivy2 stream/stream_kafka.py $(STREAM_ARGS)
	python stream/compare.py --source kafka


scale:        ## 1.12 sinh kho 5× rồi nạp vào BigQuery (dataset oulad_5x) và PostgreSQL (schema x5); chạy sau all
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 07_scale.py --factor 5
	cd etl && python 04_load_bq.py --scale 5
	cd etl && python 05_load_pg.py --scale 5

optimize:     ## 1.11 đo 4 kỹ thuật tối ưu của kho chính so với bản sao bảng thường, ghi docs/optimization.md; chạy sau make all
	python scripts/optimize.py

models:       ## mô hình phi quan hệ (BigQuery dạng lồng, PostgreSQL JSONB) so với bảng phẳng, ghi docs/data_models.md
	python scripts/data_models.py

test:
	pytest -q

test-dag:     ## DAG Airflow nạp được, đúng thứ tự, có báo lỗi; chạy trong container airflow: docker compose exec airflow make test-dag
	python -m pytest -q tests/test_dag.py tests/test_alerts.py

lock:         ## ghi phiên bản chính xác của mọi gói đang cài ra requirements.lock (chạy sau khi make test xanh)
	@{ printf '%s\n' \
	  "# Phiên bản chính xác của mọi gói trong image app, sinh bằng: make lock (đã chạy test xanh với bộ này)." \
	  "# Dockerfile cài requirements.txt với ràng buộc của file này, nên build ở máy nào, ngày nào cũng ra một bộ." \
	  "# Thêm hay đổi thư viện: sửa requirements.txt, build lại, chạy make test, rồi make lock để cập nhật file này."; \
	  pip freeze; } > requirements.lock
	@echo "Đã ghi requirements.lock ($$(grep -c '==' requirements.lock) gói)"

RUNS ?= 5
bench: ## 3.9 benchmark layouts; requires explicit CONFIRM_M3=1 after group M3 confirmation; run make load-plain first
	@test "$(CONFIRM_M3)" = "1" || { echo "Refusing benchmark: set CONFIRM_M3=1 only after the group confirms M3."; exit 2; }
	python scripts/benchmark_layouts.py run --confirm-m3 --runs $(RUNS)

app:
	streamlit run app/Home.py --server.address 0.0.0.0 --server.port 8501
