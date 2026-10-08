# Chạy TRONG container:  docker compose exec app make <lệnh>
# (Máy Windows không có make thì gõ thẳng lệnh ở dòng bên dưới mỗi mục)

.PHONY: check bq-test staging dims facts test app

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

test:
	pytest -q

app:
	streamlit run app/Home.py --server.address 0.0.0.0 --server.port 8501
